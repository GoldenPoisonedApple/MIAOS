import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from tqdm import trange


# 自作モジュールのインポート
import config

def train_model(model, train_loader, epochs):
	# モデルの初期化
	model = model.to(config.DEVICE)
	# 損失関数とオプティマイザの定義
	criterion = nn.CrossEntropyLoss()
	# lr (Learning Rate): 学習率
	# weight_decay: L = 損失 + λ*重み: デカイ重みにペナルティ: 汎化性能向上
	optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
	# 学習率スケジューラ (CosineAnnealingLR: コサインカーブに従って学習率を減衰させる)
	# T_max: 半周期のエポック数 指定のエポック数で学習率(重みの修正幅)が最小値に達するように設定
	scheduler = CosineAnnealingLR(optimizer, T_max=config.MAX_EPOCHS)

	# 学習モード: Dropout(ランダムにニューロンを無効化)、BatchNorm(バッチごとの統計量を使用)
	model.train()
	for epoch in trange(epochs, desc="Epoch", leave=False):
		# バッチごとにデータを取得、ループ
		# i=0 input: (256, 3, 32, 32) labels: (256)
		# i=1 input: (256, 3, 32, 32) labels: (256)
		for inputs, labels in train_loader:
			# data: (labels, inputs)
			# to(device): データをGPUに転送
			# non_blocking=True: 非同期にデータ転送、pin_memory=Trueとの組み合わせ
			inputs, labels = inputs.to(config.DEVICE, non_blocking=True), labels.to(config.DEVICE, non_blocking=True)
			# 勾配の初期化
			optimizer.zero_grad()
			outputs = model(inputs) # 順伝播
			loss = criterion(outputs, labels) # 損失計算
			loss.backward() # 逆伝播: 勾配を計算して各パラメータに保存
			optimizer.step() # 重みの更新
   
		# エポックごとに学習率を更新
		scheduler.step()
	return model

# 予測結果とラベルを取得
def get_predictions(model, loader):
	"""
	モデルを評価モードに切り替え、データローダーからバッチごとに入力とラベルを取得し、モデルの出力を確率に変換してリストに保存する関数。
	最終的に、すべての予測とラベルを結合して返す。
	"""
	model.eval() # 評価モード: 全結合、固定挙動
	preds = []
	labels_list = []
	with torch.no_grad(): # 評価時は勾配計算を無効化しメモリ消費を抑える
		for inputs, labels in loader:
			inputs = inputs.to(config.DEVICE, non_blocking=True)
			outputs = torch.softmax(model(inputs), dim=1) # 出力を確率に変換
			preds.append(outputs.cpu()) # outputsはGPUにあるんで、確率はCPUに転送してリストに追加
			labels_list.append(labels) # ラベルもリストに追加
	return torch.cat(preds), torch.cat(labels_list) # 複数のテンソルを一つに結合 (256, 100)*n → (256*n, 100)


def get_accuracy(model, test_loader):
	correct = 0
	total = 0
	model.eval() # 評価モード: 全結合、固定挙動
	with torch.no_grad(): # 評価時は勾配計算を無効化しメモリ消費を抑える
		for inputs, labels in test_loader:
			inputs, labels = inputs.to(config.DEVICE, non_blocking=True), labels.to(config.DEVICE, non_blocking=True)
			outputs = model(inputs) # 推論
			_, predicted = torch.max(outputs.data, 1) # 出力の最大値のインデックス取得
			# 正解数と総数を更新
			total += labels.size(0)
			correct += (predicted == labels).sum().item()
	return correct / total
