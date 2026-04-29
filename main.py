import time
import torch
import argparse
from tqdm import trange
from datetime import datetime
import os
import logging
import sys

# ROC曲線描画用に追加
import matplotlib
matplotlib.use('Agg') # GUIを持たないDocker環境での描画用バックエンド
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc
import numpy as np

import config
from dataset import dataset
from target_model import TargetCNN
from attack_model import AttackNet
from utils import train_model, get_predictions, get_accuracy, save_model, load_model

# ターゲットモデルの訓練
def train_target_model(dataset_instance, MODEL_SAVE_DIR, logger):

	p2_start_time = time.time()
	target_model = TargetCNN().to(config.DEVICE) # モデルの初期化とデバイスへの転送
	# モデルの読み込みに失敗した場合は訓練して保存
	if not load_model(target_model, os.path.join(config.ASSIGNED_MODEL_PATH, config.TARGET_MODEL_NAME)):
		trainloader, testloader, num_train, num_test = dataset_instance.get_target_dataloaders() # データ読み込み
		logger.info(f"Train: {num_train}, Test: {num_test}")
		target_model = train_model(target_model, trainloader, config.MAX_EPOCHS) # 訓練
		save_model(target_model, os.path.join(MODEL_SAVE_DIR, config.TARGET_MODEL_NAME)) # モデルの保存

	train_acc = get_accuracy(target_model, trainloader) # 訓練データに対する精度
	test_acc = get_accuracy(target_model, testloader) # テストデータに対する精度
	logger.info(f"Target Result -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})")
	logger.info(f"-> {time.time() - p2_start_time:.2f} sec")

	return target_model


# 攻撃モデルのデータセット準備
# def prepare_attack_dataset(dataset_instance, MODEL_SAVE_DIR, logger):
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
	
	logger.info(f"Attack Dataset -> Features: {attack_x.shape}, Labels: {attack_y.shape}, Classes: {attack_classes.shape}")
	logger.info(f"-> {time.time() - start_time:.2f} sec")
	
	return attack_x, attack_y, attack_classes


# 正規分布に変換
def logit_scaling(probs):
	# 丸め誤差回避
	probs = probs.to(torch.float64)
	# p=0 や p=1 による無限大を回避するための微小値クリッピング
	eps = 1e-10
	probs = torch.clamp(probs, eps, 1.0 - eps)
	return torch.log(probs / (1.0 - probs))

# 攻撃モデルのデータセット準備
def prepare_attack_dataset(dataset_instance: dataset, MODEL_SAVE_DIR, logger):
	start_time = time.time()
 
	# 今回はターゲットモデルの本物を用いる
	target_train_loader, target_test_loader, _, _ = dataset_instance.get_eval_target_dataloaders()
		
	# Offline LiRA用: サンプルごとのシャドーモデル出力(ロジット)を蓄積するリスト
	shadow_logits_in = []
	shadow_logits_out = []

	for i in trange(config.NUM_SHADOW_MODELS, desc="Shadow Models & Feature Extraction"):
		shadow_model = TargetCNN().to(config.DEVICE)
		shadow_train_loader, shadow_test_loader, _, _ = dataset_instance.get_shadow_dataloader(seed=i)
		# シャドーモデル訓練
		shadow_model = train_model(shadow_model, shadow_train_loader, config.MAX_EPOCHS)

		# ターゲットデータ(In/Out)に対する推論結果を抽出 ここではターゲットモデルの学習データを用いる
		target_p_in, target_l_in = get_predictions(shadow_model, target_train_loader)
		target_p_out, target_l_out = get_predictions(shadow_model, target_test_loader)
		
		# 正解クラスの確率を抽出し、ロジット変換
		prob_in = target_p_in[torch.arange(len(target_l_in)), target_l_in]
		prob_out = target_p_out[torch.arange(len(target_l_out)), target_l_out]
		
		shadow_logits_in.append(logit_scaling(prob_in).cpu().numpy())
		shadow_logits_out.append(logit_scaling(prob_out).cpu().numpy())
		
		del shadow_model
	
	# Offline LiRAのデータを Numpy配列 (NUM_SHADOW_MODELS x NUM_SAMPLES) に変換
	shadow_logits_in = np.array(shadow_logits_in)
	shadow_logits_out = np.array(shadow_logits_out)
	
 	# 抽出したテンソルを辞書にまとめて保存
	torch.save({
		'shadow_logits_in': shadow_logits_in, 'shadow_logits_out': shadow_logits_out
	}, os.path.join(MODEL_SAVE_DIR, config.ATTACK_DATASET_NAME))
	
	logger.info(f"Attack Dataset saved.")
	logger.info(f"-> {time.time() - start_time:.2f} sec")
	return shadow_logits_in, shadow_logits_out


# 攻撃モデルの訓練
# def train_attack_models(attack_x, attack_y, attack_classes, MODEL_SAVE_DIR, logger):
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

	logger.info(f"-> {time.time() - p4_start_time:.2f} sec")

	return attack_models


# 攻撃モデルの評価
# def evaluate_attack_models(dataset_instance, target_model, attack_models, p1_start_time, MODEL_SAVE_DIR, logger):
	p5_start_time = time.time()
	# ターゲットモデルの予測とラベルを取得
	trainloader, testloader, _, _ = dataset_instance.get_target_dataloaders() # ターゲットモデルのデータローダーを取得
	target_preds_in, target_labels_in = get_predictions(target_model, trainloader) # メンバーの予測とラベル
	target_preds_out, target_labels_out = get_predictions(target_model, testloader) # 非メンバーの予測とラベル

	class_precisions = []
	class_recalls = []
 
 
	# ROC曲線用に全クラスの確率と真のラベルを保存するリスト
	all_probs_in = []
	all_trues = []


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
			out_in = attack_model(class_preds_in.to(config.DEVICE))
			out_out = attack_model(class_preds_out.to(config.DEVICE))
			
			preds_in = out_in.cpu()
			preds_out = out_out.cpu()
			
			# クラス1(メンバー=In)の確率をSoftmaxで取得
			prob_in = torch.softmax(preds_in, dim=1)[:, 1].numpy()
			prob_out = torch.softmax(preds_out, dim=1)[:, 1].numpy()
   
		# ROC用データの集約
		all_probs_in.extend(prob_in)
		all_probs_in.extend(prob_out)
		all_trues.extend([1] * len(prob_in))
		all_trues.extend([0] * len(prob_out))

		# クラスごとの指標計算
		tp = (preds_in.argmax(dim=1) == 1).sum().item()
		fp = (preds_out.argmax(dim=1) == 1).sum().item()
		fn = (preds_in.argmax(dim=1) == 0).sum().item()

		precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
		recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

		class_precisions.append(precision)
		class_recalls.append(recall)  

	# --- ROC曲線の計算と描画 ---
	all_trues = np.array(all_trues)
	all_probs_in = np.array(all_probs_in)
	fpr, tpr, thresholds = roc_curve(all_trues, all_probs_in)
	roc_auc = auc(fpr, tpr)
	# Carlini論文に基づく対数スケールのROC曲線描画
	plt.figure(figsize=(8, 8))
	plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'Attack ROC (AUC = {roc_auc:.4f})')
	plt.plot([1e-5, 1], [1e-5, 1], color='navy', lw=2, linestyle='--', label='Random Guess')
	# 軸のスケールを対数に設定
	plt.xscale('log')
	plt.yscale('log')
	# 表示範囲の設定 (0は対数で表現できないため、極小値 1e-5 から 1.0 とする)
	plt.xlim([1e-5, 1.0])
	plt.ylim([1e-5, 1.05])
	plt.xlabel('False Positive Rate (FPR)')
	plt.ylabel('True Positive Rate (TPR)')
	plt.title('Membership Inference Attack ROC Curve (Log-Log Scale)')
	plt.legend(loc="lower right")
	plt.grid(True, which="both", ls="--", alpha=0.5)
	roc_plot_path = os.path.join(MODEL_SAVE_DIR, "roc_curve_log.png")
	plt.savefig(roc_plot_path, dpi=300, bbox_inches='tight')
	plt.close()
 
	# 特定の低FPRにおけるTPRの抽出
	# fprが特定値よりも小さい環境下での最大TPRを取得: FPRが1%の境界線に最も近い(許容値の中で最も緩い)ときの最大の攻撃成功率を取得
	tpr_at_1_fpr = tpr[fpr <= 0.01].max() if len(tpr[fpr <= 0.01]) > 0 else 0.0
	tpr_at_01_fpr = tpr[fpr <= 0.001].max() if len(tpr[fpr <= 0.001]) > 0 else 0.0
	tpr_at_001_fpr = tpr[fpr <= 0.0001].max() if len(tpr[fpr <= 0.0001]) > 0 else 0.0

	logger.info(f"Global AUC: {roc_auc:.4f}")
	logger.info(f"TPR: {tpr_at_1_fpr:.4f} at 1.0% FPR")
	logger.info(f"TPR: {tpr_at_01_fpr:.4f} at 0.1% FPR")
	logger.info(f"TPR: {tpr_at_001_fpr:.4f} at 0.01% FPR")
	logger.info(f"Saved ROC curve plot to: {roc_plot_path}")
	logger.info(f"-> {time.time() - p5_start_time:.2f} sec")
	logger.info(f"Total Time: {time.time() - p1_start_time:.2f} sec -> {(time.time() - p1_start_time)/60:.2f} min")


# 引数に shadow_logits_in, shadow_logits_out を追加
def evaluate_attack_models(dataset_instance, target_model, shadow_logits_in, shadow_logits_out, p1_start_time, MODEL_SAVE_DIR, logger):
	p5_start_time = time.time()
	trainloader, testloader, _, _ = dataset_instance.get_eval_target_dataloaders()
	target_preds_in, target_labels_in = get_predictions(target_model, trainloader)
	target_preds_out, target_labels_out = get_predictions(target_model, testloader)

	# ==========================================
	# Offline Likelihood Ratio Attack (Z-score) 評価
	# ここでのZ-scoreはターゲットデータが非メンバー（OUT）である。という帰無仮説からどれだけ逸脱しているかを示す
	# ==========================================
	# ターゲットモデルの正解クラス確率をロジット変換
	prob_in = target_preds_in[torch.arange(len(target_labels_in)), target_labels_in]
	prob_out = target_preds_out[torch.arange(len(target_labels_out)), target_labels_out]

	target_logits_in = logit_scaling(prob_in).cpu().numpy()
	target_logits_out = logit_scaling(prob_out).cpu().numpy()

	# シャドーモデル群から、サンプルごとの平均と標準偏差を計算
	mu_in = np.mean(shadow_logits_in, axis=0)
	std_in = np.std(shadow_logits_in, axis=0) + 1e-8 # ゼロ除算防止
	mu_out = np.mean(shadow_logits_out, axis=0)
	std_out = np.std(shadow_logits_out, axis=0) + 1e-8

	# 攻撃スコア = (ターゲットモデルの出力 - シャドーモデルの平均) / 標準偏差
	z_scores_in = (target_logits_in - mu_in) / std_in
	z_scores_out = (target_logits_out - mu_out) / std_out

	lira_scores = np.concatenate([z_scores_in, z_scores_out])
	lira_trues = np.concatenate([np.ones(len(z_scores_in)), np.zeros(len(z_scores_out))])

	# ==========================================
	# 攻撃スコア(Z-score)の分布をヒストグラムで可視化
	# ==========================================
	plt.figure(figsize=(10, 6))

	# スコアの最小値と最大値からビンの範囲を決定 (外れ値が大きすぎると見えなくなるためパーセンタイルでクリップ)
	min_val = np.percentile(lira_scores, 0.1)
	max_val = np.percentile(lira_scores, 99.9)
	bins = np.linspace(min_val, max_val, 100)

	# 密度(density=True)としてプロットし、2つの分布を比較しやすくする
	plt.hist(z_scores_in, bins=bins, alpha=0.6, color='royalblue', label='Members (IN)', density=True)
	plt.hist(z_scores_out, bins=bins, alpha=0.6, color='crimson', label='Non-Members (OUT)', density=True)

	plt.xlabel('Attack Score (Z-score)')
	plt.ylabel('Density')
	plt.title('Distribution of Attack Scores (Offline LiRA)')
	plt.legend(loc='upper right')
	plt.grid(True, linestyle='--', alpha=0.5)

	dist_plot_path = os.path.join(MODEL_SAVE_DIR, "score_distribution.png")
	plt.savefig(dist_plot_path, dpi=300, bbox_inches='tight')
	plt.close()

	logger.info(f"Saved score distribution plot to: {dist_plot_path}")

	# ==========================================
	# ROC曲線の描画
	# ==========================================
	fpr_lira, tpr_lira, _ = roc_curve(lira_trues, lira_scores)
	roc_auc_lira = auc(fpr_lira, tpr_lira)

	plt.figure(figsize=(8, 8))
	plt.plot(fpr_lira, tpr_lira, color='green', lw=2, label=f'Offline LiRA (AUC = {roc_auc_lira:.4f})')
	plt.plot([1e-5, 1], [1e-5, 1], color='navy', lw=2, linestyle='--', label='Random Guess')

	plt.xscale('log')
	plt.yscale('log')
	plt.xlim([1e-5, 1.0])
	plt.ylim([1e-5, 1.05])
	plt.xlabel('False Positive Rate (FPR)')
	plt.ylabel('True Positive Rate (TPR)')
	plt.title('Membership Inference Attack ROC Curve (Log-Log Scale)')
	plt.legend(loc="lower right")
	plt.grid(True, which="both", ls="--", alpha=0.5)

	roc_plot_path = os.path.join(MODEL_SAVE_DIR, "roc_curve_lira_log.png")
	plt.savefig(roc_plot_path, dpi=300, bbox_inches='tight')
	plt.close()
 
	# ログ出力    
	logger.info(f"--- Offline LiRA Results ---")
	logger.info(f"Global AUC: {roc_auc_lira:.4f}")
 
	tpr_at_1_fpr = tpr_lira[fpr_lira <= 0.01].max() if len(tpr_lira[fpr_lira <= 0.01]) > 0 else 0.0
	tpr_at_01_fpr = tpr_lira[fpr_lira <= 0.001].max() if len(tpr_lira[fpr_lira <= 0.001]) > 0 else 0.0
	tpr_at_001_fpr = tpr_lira[fpr_lira <= 0.0001].max() if len(tpr_lira[fpr_lira <= 0.0001]) > 0 else 0.0

	logger.info(f"TPR: {tpr_at_1_fpr:.4f} at 1.0% FPR")
	logger.info(f"TPR: {tpr_at_01_fpr:.4f} at 0.1% FPR")
	logger.info(f"TPR: {tpr_at_001_fpr:.4f} at 0.01% FPR")
	logger.info(f"Saved ROC curve plot to: {roc_plot_path}")
	logger.info(f"-> {time.time() - p5_start_time:.2f} sec")
	logger.info(f"Total Time: {time.time() - p1_start_time:.2f} sec -> {(time.time() - p1_start_time)/60:.2f} min")


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
   
	# ロガー
	log_file_path = os.path.join(MODEL_SAVE_DIR, "execution.log")
	logging.basicConfig(
		level=logging.INFO,
		format='%(asctime)s [%(levelname)s] %(message)s',
		handlers=[
			logging.FileHandler(log_file_path), # ファイルへの出力
			logging.StreamHandler(sys.stdout)   # 標準出力(ターミナル)への出力
		]
	)
	logger = logging.getLogger(__name__)

	# 設定の表示
	logger.info("Configurations:")
	for key in dir(config):
		if key.isupper():  # 大文字だけ表示
			logger.info(f"  {key}: {getattr(config, key)}")
	logger.info(f"Model Save Directory: {MODEL_SAVE_DIR}")
	logger.info(f"Assigned Model Path: {assigned_model_path}")
	logger.info(f"is_assigned_model_path: {is_assigned_model_path}")


	# ----------------------------------
	# データセットの準備
	# ----------------------------------
	logger.info("[Phase 1] Preparing data...")
	p1_start_time = time.time()
	if is_assigned_model_path:
		dataset_instance = dataset(MODEL_SAVE_DIR, assigned_model_path=assigned_model_path)
	else:
		dataset_instance = dataset(MODEL_SAVE_DIR)
	logger.info(f"-> {time.time() - p1_start_time:.2f} sec")

	# ----------------------------------
	# ターゲットモデルの訓練と評価
	# ----------------------------------
	logger.info("[Phase 2] Training target model...")
	target_model = TargetCNN().to(config.DEVICE)
	if not args.load_target_model:
		target_model = train_target_model(dataset_instance, MODEL_SAVE_DIR, logger)
	else:
		load_model(target_model, os.path.join(assigned_model_path, config.TARGET_MODEL_NAME))
		logger.info("Loading complete")
  
	# ----------------------------------
	# 攻撃モデルのデータセット作成
	# ----------------------------------
	logger.info(f"[Phase 3] Preparing attack dataset...")
	shadow_logits_in, shadow_logits_out = [], []
	if not args.load_attack_dataset:
		shadow_logits_in, shadow_logits_out = prepare_attack_dataset(dataset_instance, MODEL_SAVE_DIR, logger)
	else:
		# テンソルを含む辞書をロード
		data = torch.load(os.path.join(assigned_model_path, config.ATTACK_DATASET_NAME), map_location='cpu', weights_only=True)
		shadow_logits_in = data['shadow_logits_in']
		shadow_logits_out = data['shadow_logits_out']
		logger.info("Loading complete")
  
	# ----------------------------------
	# 攻撃モデルの訓練
	# ----------------------------------
	# logger.info("[Phase 4] Training attack model...")
	# attack_models = {}
	# if not args.load_attack_models:
	# 	attack_models = train_attack_models(attack_x, attack_y, attack_classes, MODEL_SAVE_DIR, logger)
	# else:
	# 	for class_idx in range(config.NUM_CLASSES):
	# 		attack_model = AttackNet(input_dim=config.NUM_CLASSES).to(config.DEVICE)
	# 		load_model(attack_model, os.path.join(assigned_model_path, config.ATTACK_MODEL_NAME_TEMPLATE.format(class_idx)))
	# 		attack_models[class_idx] = attack_model
	# 	logger.info("Loading complete")


	# ----------------------------------
	# 攻撃モデルの評価
	# ----------------------------------
	logger.info("[Phase 5] Evaluating attack model...")
	evaluate_attack_models(dataset_instance, target_model, shadow_logits_in, shadow_logits_out, p1_start_time, MODEL_SAVE_DIR, logger)



if __name__ == "__main__":
	main()