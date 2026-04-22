import time
import torch
from tqdm import trange

import config
from dataset import dataset
from target_model import TargetCNN
from attack_model import AttackNet
from utils import train_model, get_predictions, get_accuracy


def main():
	# 設定の表示
	print("Configurations:")
	for key in dir(config):
		if key.isupper():  # 大文字だけ表示
			print(f"  {key}: {getattr(config, key)}")
   
	# データセットの準備
	print("\n[Phase 1] Preparing data...")
	p1_start_time = time.time()
	dataset_instance = dataset()
	trainloader, testloader, num_train, num_test = dataset_instance.get_target_dataloaders()
	print(f"Train: {num_train}, Test: {num_test}")
	print(f"-> {time.time() - p1_start_time:.2f} sec")
 
	# ターゲットモデルの訓練と評価
	print("\n[Phase 2] Training target model...")
	p2_start_time = time.time()
	target_model = TargetCNN().to(config.DEVICE) # モデルの初期化とデバイスへの転送
	target_model = train_model(target_model, trainloader, config.MAX_EPOCHS) # 訓練
	train_acc = get_accuracy(target_model, trainloader) # 訓練データに対する精度
	test_acc = get_accuracy(target_model, testloader) # テストデータに対する精度
	print(f"Target Result -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})")
	print(f"-> {time.time() - p2_start_time:.2f} sec")
 
	# シャドーモデルの訓練
	print(f"\n[Phase 3] Training shadow models...")
	p3_start_time = time.time()
	attack_x, attack_y, attack_classes = [], [], []
	for i in trange(config.NUM_SHADOW_MODELS, desc="Shadow Models"):
		shadow_train_loader, shadow_test_loader, _, _ = dataset_instance.get_shadow_dataloader() # シャドーモデルのデータローダーを取得
		shadow_model = TargetCNN().to(config.DEVICE) # シャドーモデルの初期化とデバイスへの転送
		shadow_model = train_model(shadow_model, shadow_train_loader, config.MAX_EPOCHS) # シャドーモデルの訓練
		
		preds_in, labels_in = get_predictions(shadow_model, shadow_train_loader) # シャドーモデルの訓練データに対する予測とラベルを取得
		preds_out, labels_out = get_predictions(shadow_model, shadow_test_loader) # シャドーモデルのテストデータに対する予測とラベルを取得
		
		attack_x.append(preds_in.cpu()) # 訓練データの予測を攻撃用特徴量リストに追加
		attack_y.append(torch.ones(len(labels_in), dtype=torch.long)) # 訓練データはメンバなので1を追加
		attack_classes.append(labels_in.cpu()) # 訓練データのクラスラベルをリストに追加
		
		attack_x.append(preds_out.cpu()) # テストデータの予測を攻撃用特徴量リストに追加
		attack_y.append(torch.zeros(len(labels_out), dtype=torch.long)) # テストデータは非メンバなので0を追加
		attack_classes.append(labels_out.cpu()) # テストデータのクラスラベルをリストに追加
  
	attack_x = torch.cat(attack_x) # 攻撃用特徴量を一つのテンソルに結合
	attack_y = torch.cat(attack_y) # 攻撃用ラベルを一つのテンソルに結合
	attack_classes = torch.cat(attack_classes) # 攻撃用クラスラベルを一つのテンソルに結合
	print(f"Attack Dataset -> Features: {attack_x.shape}, Labels: {attack_y.shape}, Classes: {attack_classes.shape}")
	print(f"-> {time.time() - p3_start_time:.2f} sec")

	# 攻撃モデルの訓練
	print("\n[Phase 4] Training attack model...")
	p4_start_time = time.time()
	
	attack_models = {}
	for class_idx in trange(config.NUM_CLASSES, desc="Attack Models"):
		class_mask = (attack_classes == class_idx) # クラスごとのマスクを作成
		if class_mask.sum() == 0: # クラスにデータがない場合はスキップ
			continue

		# クラスごとの攻撃用特徴量とラベルを抽出
		class_attack_x = attack_x[class_mask]
		class_attack_y = attack_y[class_mask]
		# データセット作成
		class_dataset = torch.utils.data.TensorDataset(class_attack_x, class_attack_y)
		class_loader = torch.utils.data.DataLoader(class_dataset, batch_size=config.BATCH_SIZE, shuffle=True, num_workers=config.NUM_WORKERS, pin_memory=True)
	
		# 訓練
		attack_model = AttackNet(input_dim=config.NUM_CLASSES).to(config.DEVICE) # 攻撃モデルの初期化とデバイスへの転送
		attack_model = train_model(attack_model, class_loader, config.MAX_EPOCHS)
		attack_models[class_idx] = attack_model # クラスごとの攻撃モデルを辞書に保存

	print(f"-> {time.time() - p4_start_time:.2f} sec")
 
 
	# 攻撃モデルの評価
	print("\n[Phase 5] Evaluating attack model...")
	p5_start_time = time.time()
	# ターゲットモデルの予測とラベルを取得
	target_preds_in, target_labels_in = get_predictions(target_model, trainloader) # メンバーの予測とラベル
	target_preds_out, target_labels_out = get_predictions(target_model, testloader) # 非メンバーの予測とラベル
 
	eval_preds = []
	eval_trues = []
	eval_classes = []
	
 
	class_amounts = torch.bincount(attack_classes) # クラスごとのデータ数をカウント
	print(f"Class Distribution in Attack Dataset: {class_amounts}")
 
 
	for class_idx in trange(config.NUM_CLASSES, desc="Evaluating Classes"):
		if class_idx not in attack_models: # クラスに攻撃モデルがない場合はスキップ
			continue
		
		attack_model = attack_models[class_idx] # クラスごとの攻撃モデルを取得
		
		# ターゲットモデルのメンバーと非メンバーの予測とラベルをクラスごとにマスク
		class_mask_in = (target_labels_in == class_idx)
		class_mask_out = (target_labels_out == class_idx)
		# 抽出 Trueのやつだけ残す
		class_preds_in = target_preds_in[class_mask_in]
		class_preds_out = target_preds_out[class_mask_out]

		class_trues_in = torch.ones(len(class_preds_in)) # メンバーは1
		class_trues_out = torch.zeros(len(class_preds_out)) # 非メンバーは0
  
		# 攻撃モデルで予測
		with torch.no_grad():
			class_eval_preds_in = attack_model(class_preds_in.to(config.DEVICE)).cpu() # メンバーの予測
			class_eval_preds_out = attack_model(class_preds_out.to(config.DEVICE)).cpu() # 非メンバーの予測
   
		eval_preds.append(torch.cat([class_eval_preds_in, class_eval_preds_out])) # 予測をリストに追加
		eval_trues.append(torch.cat([class_trues_in, class_trues_out])) # 真のラベルをリストに追加
		eval_classes.append(torch.cat([torch.full_like(class_trues_in, class_idx), torch.full_like(class_trues_out, class_idx)])) # クラスラベルをリストに追加
  
	eval_preds = torch.cat(eval_preds) # すべての予測を一つのテンソルに結合
	eval_trues = torch.cat(eval_trues) # すべての真のラベルを一つのテンソルに結合
	eval_classes = torch.cat(eval_classes) # すべてのクラスラベルを一つのテンソルに結合
	print(f"Evaluation Dataset -> Predictions: {eval_preds.shape}, Trues: {eval_trues.shape}, Classes: {eval_classes.shape}")
	print(f"-> {time.time() - p5_start_time:.2f} sec")
 
	# Precision: TP / (TP + FP)
	# Recall: TP / (TP + FN)
	tp = ((eval_preds.argmax(dim=1) == 1) & (eval_trues == 1)).sum().item() # 真陽性
	fp = ((eval_preds.argmax(dim=1) == 1) & (eval_trues == 0)).sum().item() # 偽陽性
	fn = ((eval_preds.argmax(dim=1) == 0) & (eval_trues == 1)).sum().item() # 偽陰性
	precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0 # Precisionの計算
	recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0 # Recallの計算
 
	print(f"Attack Model Evaluation -> Precision: {precision:.4f}, Recall: {recall:.4f}")
  
  
  
  
if __name__ == "__main__":
	main()