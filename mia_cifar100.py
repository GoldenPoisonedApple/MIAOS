import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Subset
from sklearn.metrics import precision_score, recall_score
import time

class TargetModel(nn.Module):
	"""
	ターゲットモデルおよびシャドウモデルのアーキテクチャ。
	"""
	def __init__(self):
		super(TargetModel, self).__init__()
		# features: 特徴量抽出器
		# in_channels: 入力チャネル数 RGBなので3
		# out_channels: 出力チャネル数 32個のフィルタを使用するので32種類の特徴マップが出力される
		# kernel_size: カーネル=フィルタのサイズ 3x3のフィルタを使用
		# stride: ストライド幅
		# padding: パディング幅　畳み込みの出力サイズを入力と同じにするために1ピクセルのパディングを追加
		self.features = nn.Sequential(
			nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3, padding=1),	# Conv2d: 2次元畳み込み層
			nn.Tanh(),	# 活性化関数 -1～1
			nn.MaxPool2d(kernel_size=2, stride=2),	# 特徴マップの空間サイズを半分に 範囲(2x2)の最大値を採用
			nn.Conv2d(in_channels=32, out_channels=64, kernel_size=3, padding=1),
			nn.Tanh(),
			nn.MaxPool2d(kernel_size=2, stride=2)
		)
		# classifier: 分類器
		# in_features: 入力特徴量数 (64チャネル * 8 * 8)
		# out_features: 出力特徴量数
		self.classifier = nn.Sequential(
			nn.Linear(in_features=64 * 8 * 8, out_features=128), # 全結合層 チャネル64 * サイズ 8*8 の特徴を128種類(ベクトル)に変換
			nn.Tanh(),
			nn.Linear(in_features=128, out_features=100) # 出力層 クラス数100に対応する出力を生成
			# 訓練時はCrossEntropyLossでSoftMaxが内包されるため、ここではロジットを出力する
		)

	def forward(self, x):
		x = self.features(x) # 入力画像を特徴マップに変換
		x = x.view(x.size(0), -1) # テンソルを1次元ベクトルに平坦化 (チャネル数 * 高さ * 幅)の3次元テンソルを1次元ベクトルに変換
		x = self.classifier(x) # 分類
		return x

class AttackModel(nn.Module):
	"""
	クラスごとに構築するアタックモデル（二値分類器）。
	"""
	def __init__(self, num_classes=100):
		super(AttackModel, self).__init__()
		self.fc = nn.Sequential(
			nn.Linear(in_features=num_classes, out_features=64), # 論文ではサイズ64の隠れ層を使用
			nn.ReLU(),
			nn.Linear(in_features=64, out_features=2) # クラス: 0 (out), 1 (in)
		)

	def forward(self, x):
		return self.fc(x)
	

# ==========================================
# 2. データセット準備
# ==========================================
def prepare_datasets(train_size, batch_size):
	"""
	CIFAR-100データセットをダウンロードし、ターゲット用とシャドウ用に分割する。
	"""
	
	# データ前処理: テンソル化と正規化
	transform = transforms.Compose([
		transforms.ToTensor(),
		transforms.Normalize((0.5071, 0.4867, 0.4408), (0.2675, 0.2565, 0.2761))
	])
	
	# root: データセットの保存先ディレクトリ
	# train: 訓練データ(True)かテストデータ(False)か
	# download: 自動ダウンロードするか否か
	full_train = torchvision.datasets.CIFAR100(root='./data', train=True, download=True, transform=transform)
	full_test = torchvision.datasets.CIFAR100(root='./data', train=False, download=True, transform=transform)
	
	# データセットのインデックスをランダムにシャッフル
	indices = np.random.permutation(len(full_train)) # シャッフルインデックス生成 [3, 0, 4, 1, 2]
	
	# ターゲットモデル用データ（train_size分を抽出）
	target_train_idx = indices[:train_size] # シャッフルインデックスから最初のtrain_size個を取得
	target_train = Subset(full_train, target_train_idx) # そのインデックスに対応するデータをSubsetで抽出
	# ターゲットモデル評価用 訓練と同数
	target_test_idx = np.random.permutation(len(full_test))[:train_size]
	target_test = Subset(full_test, target_test_idx)

	# シャドーモデル用 重複しない
	shadow_pool_idx = indices[train_size:]

	# DataLoader: ミニバッチを作成するためのイテレータ
	# shuffle: エポックごとにデータをシャッフルするか否か    
	target_train_loader = DataLoader(target_train, batch_size=batch_size, shuffle=True)
	target_test_loader = DataLoader(target_test, batch_size=batch_size, shuffle=False) # ここでのテストデータはモデルの評価用
	
	return target_train_loader, target_test_loader, full_train, shadow_pool_idx, full_test

# モデルの学習
def train_model(model, train_loader, epochs=100, device='cuda', lr=0.001, weight_decay=1e-07):
	"""
	モデルの学習プロセス。
	"""
	model.to(device)
	criterion = nn.CrossEntropyLoss()
	# lr: learning rate (学習率)
	# weight_decay: L2正則化の係数。論文におけるlearning rate decayを近似する意味合いも持つ。
	optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
	
	model.train()
	for epoch in range(epochs):
		for inputs, targets in train_loader:
			inputs, targets = inputs.to(device), targets.to(device)
			optimizer.zero_grad() # 勾配の初期化
			outputs = model(inputs)
			loss = criterion(outputs, targets)
			loss.backward() # 誤差逆伝播
			optimizer.step() # パラメータ更新
	return model

def get_predictions(model, dataloader, device, is_member):
	"""モデルから予測確率ベクトルとラベルを取得する [cite: 181, 185]"""
	model.eval()
	probs_list, labels_list, membership_list = [], [], []
	with torch.no_grad():
		for inputs, targets in dataloader:
			inputs = inputs.to(device)
			outputs = model(inputs)
			probs = F.softmax(outputs, dim=1).cpu().numpy()
			probs_list.append(probs)
			labels_list.append(targets.numpy())
			membership_list.append(np.full(targets.size(0), is_member))
			
	return np.vstack(probs_list), np.concatenate(labels_list), np.concatenate(membership_list)

def main():
	parser = argparse.ArgumentParser(description="Membership Inference Attack on CIFAR-100")
	parser.add_argument('--train_size', type=int, default=10520, help="Size of target training dataset [cite: 447]")
	parser.add_argument('--num_shadows', type=int, default=10, help="Number of shadow models ")
	parser.add_argument('--epochs', type=int, default=100, help="Training epochs for target/shadow models ")
	parser.add_argument('--batch_size', type=int, default=128, help="Batch size for training")
	parser.add_argument('--lr', type=float, default=0.001, help="Learning rate ")
	args = parser.parse_args()

	device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
	print(f"Using device: {device}")

	# データセット準備
	print("Preparing datasets...")
	t_train_loader, t_test_loader, full_train, shadow_pool_idx, full_test = prepare_datasets(args.train_size, args.batch_size)

	# 1. ターゲットモデルの学習
	print(f"\nTraining Target Model on {args.train_size} samples for {args.epochs} epochs...")
	target_model = CNN(num_classes=100)
	train_model(target_model, t_train_loader, args.epochs, args.lr, device)

	# 2. シャドウモデル群の学習と攻撃用訓練データの収集 [cite: 176, 260]
	attack_X, attack_Y, attack_classes = [], [], []
	for i in range(args.num_shadows):
		print(f"\nTraining Shadow Model {i+1}/{args.num_shadows}...")
		# シャドウモデル用のデータをプールからランダムサンプリング（ターゲットとは重複しない） 
		s_train_idx = np.random.choice(shadow_pool_idx, size=args.train_size, replace=False)
		s_train = Subset(full_train, s_train_idx)
		s_train_loader = DataLoader(s_train, batch_size=args.batch_size, shuffle=True)
		
		# シャドウテスト用データ（訓練に使っていないもの） [cite: 261]
		s_test_idx = np.random.permutation(len(full_test))[:args.train_size]
		s_test = Subset(full_test, s_test_idx)
		s_test_loader = DataLoader(s_test, batch_size=args.batch_size, shuffle=False)

		shadow_model = CNN(num_classes=100)
		train_model(shadow_model, s_train_loader, args.epochs, args.lr, device)

		# 予測の収集 ("in" = 1, "out" = 0) [cite: 262]
		p_in, l_in, m_in = get_predictions(shadow_model, s_train_loader, device, is_member=1)
		p_out, l_out, m_out = get_predictions(shadow_model, s_test_loader, device, is_member=0)
		
		attack_X.extend([p_in, p_out])
		attack_Y.extend([m_in, m_out])
		attack_classes.extend([l_in, l_out])

	attack_X = np.vstack(attack_X)
	attack_Y = np.concatenate(attack_Y)
	attack_classes = np.concatenate(attack_classes)

	# 3. アタックモデル群の学習（クラスごとに構築） [cite: 173]
	print("\nTraining Attack Models...")
	attack_models = [AttackModel(num_classes=100).to(device) for _ in range(100)]
	criterion = nn.CrossEntropyLoss()
	
	for c in range(100):
		idx = np.where(attack_classes == c)[0]
		if len(idx) == 0: continue
		
		X_c = torch.tensor(attack_X[idx], dtype=torch.float32)
		Y_c = torch.tensor(attack_Y[idx], dtype=torch.long)
		dataset_c = torch.utils.data.TensorDataset(X_c, Y_c)
		loader_c = DataLoader(dataset_c, batch_size=64, shuffle=True)
		
		optimizer = optim.Adam(attack_models[c].parameters(), lr=0.001)
		attack_models[c].train()
		for epoch in range(50):
			for inputs, targets in loader_c:
				inputs, targets = inputs.to(device), targets.to(device)
				optimizer.zero_grad()
				loss = criterion(attack_models[c](inputs), targets)
				loss.backward()
				optimizer.step()

	# 4. ターゲットモデルに対する攻撃の実行と評価 [cite: 499, 502]
	print("\nEvaluating Attack Models against Target Model...")
	t_p_in, t_l_in, t_m_in = get_predictions(target_model, t_train_loader, device, is_member=1)
	t_p_out, t_l_out, t_m_out = get_predictions(target_model, t_test_loader, device, is_member=0)
	
	eval_X = np.vstack([t_p_in, t_p_out])
	eval_Y = np.concatenate([t_m_in, t_m_out])
	eval_classes = np.concatenate([t_l_in, t_l_out])

	preds = []
	for i in range(len(eval_X)):
		c = eval_classes[i]
		x = torch.tensor(eval_X[i], dtype=torch.float32).unsqueeze(0).to(device)
		attack_models[c].eval()
		with torch.no_grad():
			out = attack_models[c](x)
			pred = torch.argmax(out, dim=1).item()
			preds.append(pred)

	# 適合率(Precision)と再現率(Recall)の計算 [cite: 503, 504]
	precision = precision_score(eval_Y, preds)
	recall = recall_score(eval_Y, preds)
	
	print("\n--- Attack Evaluation Results ---")
	print(f"Overall Precision: {precision:.4f}")
	print(f"Overall Recall:    {recall:.4f}")
	print("---------------------------------")

if __name__ == '__main__':
	main()