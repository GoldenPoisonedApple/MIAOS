import time
import torch
import argparse
from tqdm import trange
from datetime import datetime
import os


import config
from dataset import dataset
from target_model import TargetCNN
from attack_model import AttackNet
from utils import train_model, get_predictions, get_accuracy, save_model, load_model

# ターゲットモデルの訓練
def train_target_model(dataset_instance, MODEL_SAVE_DIR):

	p2_start_time = time.time()
	target_model = TargetCNN().to(config.DEVICE) # モデルの初期化とデバイスへの転送
	# モデルの読み込みに失敗した場合は訓練して保存
	if not load_model(target_model, os.path.join(config.ASSIGNED_MODEL_PATH, config.TARGET_MODEL_NAME)):
		trainloader, testloader, num_train, num_test = dataset_instance.get_target_dataloaders() # データ読み込み
		print(f"Train: {num_train}, Test: {num_test}")
		target_model = train_model(target_model, trainloader, config.MAX_EPOCHS) # 訓練
		save_model(target_model, os.path.join(MODEL_SAVE_DIR, config.TARGET_MODEL_NAME)) # モデルの保存

	train_acc = get_accuracy(target_model, trainloader) # 訓練データに対する精度
	test_acc = get_accuracy(target_model, testloader) # テストデータに対する精度
	print(f"Target Result -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})")
	print(f"-> {time.time() - p2_start_time:.2f} sec")

	return target_model


# 攻撃モデルのデータセット準備
def prepare_attack_dataset(dataset_instance, MODEL_SAVE_DIR):
	start_time = time.time()
	
	attack_x, attack_y, attack_classes = [], [], []
	for i in trange(config.NUM_SHADOW_MODELS, desc="Shadow Models & Feature Extraction"):
		shadow_model = TargetCNN().to(config.DEVICE)
		shadow_train_loader, shadow_test_loader, _, _ = dataset_instance.get_shadow_dataloader(seed=i)
		
		# シャドーモデルの訓練と予測値の抽出
		shadow_model = train_model(shadow_model, shadow_train_loader, config.MAX_EPOCHS)

		# 予測値の抽出
		preds_in, labels_in = get_predictions(shadow_model, shadow_train_loader)
		preds_out, labels_out = get_predictions(shadow_model, shadow_test_loader)
		
		attack_x.append(preds_in.cpu())
		attack_y.append(torch.ones(len(labels_in), dtype=torch.long))
		attack_classes.append(labels_in.cpu())
		
		attack_x.append(preds_out.cpu())
		attack_y.append(torch.zeros(len(labels_out), dtype=torch.long))
		attack_classes.append(labels_out.cpu())
		
		# メモリ解放
		del shadow_model

	# 一つのテンソルに結合
	attack_x = torch.cat(attack_x)
	attack_y = torch.cat(attack_y)
	attack_classes = torch.cat(attack_classes)
	
	# 3. 抽出したテンソルを辞書にまとめて保存
	torch.save({
		'x': attack_x,
		'y': attack_y,
		'classes': attack_classes
	}, os.path.join(MODEL_SAVE_DIR, config.ATTACK_DATASET_NAME))
	
	print(f"Attack Dataset -> Features: {attack_x.shape}, Labels: {attack_y.shape}, Classes: {attack_classes.shape}")
	print(f"-> {time.time() - start_time:.2f} sec")
	
	return attack_x, attack_y, attack_classes


# 攻撃モデルの訓練
def train_attack_models(attack_x, attack_y, attack_classes, MODEL_SAVE_DIR):
	p4_start_time = time.time()
	
	# クラスごとに攻撃モデルを訓練
	attack_models = {}
	for class_idx in trange(config.NUM_CLASSES, desc="Attack Models"):
		class_mask = (attack_classes == class_idx) # クラスごとのマスクを作成
		if class_mask.sum() == 0: # クラスにデータがない場合はスキップ
			continue
		attack_model = AttackNet(input_dim=config.NUM_CLASSES).to(config.DEVICE) # 攻撃モデルの初期化とデバイスへの転送
		if not load_model(attack_model, os.path.join(config.ASSIGNED_MODEL_PATH, config.ATTACK_MODEL_NAME_TEMPLATE.format(class_idx))):
			# クラスごとの攻撃用特徴量とラベルを抽出
			class_attack_x = attack_x[class_mask]
			class_attack_y = attack_y[class_mask]
			# データセット作成
			class_dataset = torch.utils.data.TensorDataset(class_attack_x, class_attack_y)
			class_loader = torch.utils.data.DataLoader(class_dataset, batch_size=config.BATCH_SIZE, shuffle=True, num_workers=config.NUM_WORKERS, pin_memory=True)
			# 攻撃モデルの訓練
			attack_model = train_model(attack_model, class_loader, config.MAX_EPOCHS)
			save_model(attack_model, os.path.join(MODEL_SAVE_DIR, config.ATTACK_MODEL_NAME_TEMPLATE.format(class_idx))) # モデルの保存

		attack_models[class_idx] = attack_model # クラスごとの攻撃モデルを辞書に保存

	print(f"-> {time.time() - p4_start_time:.2f} sec")

	return attack_models


# 攻撃モデルの評価
def evaluate_attack_models(dataset_instance, target_model, attack_models, p1_start_time):
	p5_start_time = time.time()
	# ターゲットモデルの予測とラベルを取得
	trainloader, testloader, _, _ = dataset_instance.get_target_dataloaders() # ターゲットモデルのデータローダーを取得
	target_preds_in, target_labels_in = get_predictions(target_model, trainloader) # メンバーの予測とラベル
	target_preds_out, target_labels_out = get_predictions(target_model, testloader) # 非メンバーの予測とラベル

	class_precisions = []
	class_recalls = []	


	for class_idx in trange(config.NUM_CLASSES, desc="Evaluating Classes"):
		if class_idx not in attack_models: # クラスに攻撃モデルがない場合はスキップ
			continue
		
		attack_model = attack_models[class_idx] # クラスごとの攻撃モデルを取得
		
		# マスク作成
		class_mask_in = (target_labels_in == class_idx)
		class_mask_out = (target_labels_out == class_idx)
		# 抽出 Trueのやつだけ残す
		class_preds_in = target_preds_in[class_mask_in]
		class_preds_out = target_preds_out[class_mask_out]

		if len(class_preds_in) == 0 or len(class_preds_out) == 0:
			continue

		# 攻撃モデルで予測
		with torch.no_grad():
			preds_in = attack_model(class_preds_in.to(config.DEVICE)).cpu() # メンバーの予測
			preds_out = attack_model(class_preds_out.to(config.DEVICE)).cpu() # 非メンバーの予測

		# クラスごとの指標計算
		tp = (preds_in.argmax(dim=1) == 1).sum().item()
		fp = (preds_out.argmax(dim=1) == 1).sum().item()
		fn = (preds_in.argmax(dim=1) == 0).sum().item()

		precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
		recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

		class_precisions.append(precision)
		class_recalls.append(recall)  


	# 統計量の表示 (論文に準じて中央値を採用)
	print(f"\nAttack Model Evaluation:")
	# print("class_precisions:", [f"{x:.4f}" for x in class_precisions])
	# print("class_recalls:", [f"{x:.4f}" for x in class_recalls])
	import numpy as np
	print(f"Precision Median: {np.median(class_precisions):.4f}")
	print(f"Precision Variance: {np.var(class_precisions):.4f}")
	print(f"Recall Median: {np.median(class_recalls):.4f}")
	print(f"Recall Variance: {np.var(class_recalls):.4f}")
	print(f"-> {time.time() - p5_start_time:.2f} sec")

	print(f"\nTotal Time: {time.time() - p1_start_time:.2f} sec")



def main():
	# 引数処理
	parser = argparse.ArgumentParser(description="Membership Inference Attack on CIFAR-100")
	parser.add_argument('--assigned_model_path', type=str, default="", help="Path to load pre-trained models")
	parser.add_argument('--notes', type=str, default="", help="Special notes")	
	parser.add_argument('--load_target_model', action='store_true', default=False, help="Whether to load pre-trained target model")
	parser.add_argument('--load_attack_dataset', action='store_true', default=False, help="Whether to load pre-trained shadow models")
	parser.add_argument('--load_attack_models', action='store_true', default=False, help="Whether to load pre-trained attack models")
	args = parser.parse_args()

	is_assigned_model_path = (not args.assigned_model_path == "")

	# パス整形
	assigned_model_path = args.assigned_model_path.strip() # パスの前後の空白を削除
	assigned_model_path = os.path.join(config.MODEL_DIR, assigned_model_path)
	# 早期終了判定
	if is_assigned_model_path:
		# 指定されたパスのディレクトリが存在しない場合早期終了
		if not os.path.exists(assigned_model_path):
			print(f"Error: Assigned model path '{assigned_model_path}' does not exist.")
			return
		# パスを指定しているのにモデルを読み込まない場合早期終了
		if (not args.load_target_model) and (not args.load_attack_dataset) and (not args.load_attack_models):
			print("Error: No model to load. Please specify the model to load.")
			return

	# 保存ディレクトリ作成
	timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
	if args.notes != "":
		timestamp = timestamp + "_" + args.notes
	MODEL_SAVE_DIR = os.path.join(config.MODEL_DIR, timestamp)
	os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
	# メタ情報保存
	with open(os.path.join(MODEL_SAVE_DIR, "specification.txt"), "w") as f:
		f.write("Configurations:\n")
		for key in dir(config):
			if key.isupper():  # 大文字だけ表示
				f.write(f"{key}: {getattr(config, key)}\n")
		f.write(f"Arguments:\n")
		for key in args.__dict__.keys():
			f.write(f"{key}: {args.__dict__[key]}\n")

	# 設定の表示
	print("Configurations:")
	for key in dir(config):
		if key.isupper():  # 大文字だけ表示
			print(f"  {key}: {getattr(config, key)}")
	print(f"Model Save Directory: {MODEL_SAVE_DIR}")
	print(f"Assigned Model Path: {assigned_model_path}")
	print(f"is_assigned_model_path: {is_assigned_model_path}")


	# ----------------------------------
	# データセットの準備
	# ----------------------------------
	print("\n[Phase 1] Preparing data...")
	p1_start_time = time.time()
	if is_assigned_model_path:
		dataset_instance = dataset(MODEL_SAVE_DIR, assigned_model_path=assigned_model_path)
	else:
		dataset_instance = dataset(MODEL_SAVE_DIR)
	print(f"-> {time.time() - p1_start_time:.2f} sec")

	# ----------------------------------
	# ターゲットモデルの訓練と評価
	# ----------------------------------
	print("\n[Phase 2] Training target model...")
	target_model = TargetCNN().to(config.DEVICE)
	if not args.load_target_model:
		target_model = train_target_model(dataset_instance, MODEL_SAVE_DIR)
	else:
		load_model(target_model, os.path.join(assigned_model_path, config.TARGET_MODEL_NAME))
		print("Loading complete")
  
	# ----------------------------------
	# 攻撃モデルのデータセット作成
	# ----------------------------------
	print(f"\n[Phase 3] Preparing attack dataset...")
	attack_x, attack_y, attack_classes = [], [], []
	if not args.load_attack_dataset:
		attack_x, attack_y, attack_classes = prepare_attack_dataset(dataset_instance, MODEL_SAVE_DIR)
	else:
		# テンソルを含む辞書をロード
		data = torch.load(os.path.join(assigned_model_path, config.ATTACK_DATASET_NAME), map_location='cpu')
		attack_x = data['x']
		attack_y = data['y']
		attack_classes = data['classes']
		print("Loading complete")

  
	# ----------------------------------
	# 攻撃モデルの訓練
	# ----------------------------------
	print("\n[Phase 4] Training attack model...")
	attack_models = {}
	if not args.load_attack_models:
		attack_models = train_attack_models(attack_x, attack_y, attack_classes, MODEL_SAVE_DIR)
	else:
		for class_idx in range(config.NUM_CLASSES):
			attack_model = AttackNet(input_dim=config.NUM_CLASSES).to(config.DEVICE)
			load_model(attack_model, os.path.join(assigned_model_path, config.ATTACK_MODEL_NAME_TEMPLATE.format(class_idx)))
			attack_models[class_idx] = attack_model
		print("Loading complete")


	# ----------------------------------
	# 攻撃モデルの評価
	# ----------------------------------
	print("\n[Phase 5] Evaluating attack model...")
	evaluate_attack_models(dataset_instance, target_model, attack_models, p1_start_time)



if __name__ == "__main__":
	main()