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

import config
from dataset import dataset
from target_model import TargetCNN
from mia_attack import MIA_Attack
from mia_lira import MIA_LIRA
from mia_shokri import MIA_Shokri

def main():
	# 引数処理
	parser = argparse.ArgumentParser(description="Membership Inference Attack on CIFAR-100")
	parser.add_argument('--assigned_model_path', type=str, default="", help="Path to load pre-trained models")
	parser.add_argument('--notes', type=str, default="", help="Special notes")	
	parser.add_argument('--load_target_model', action='store_true', default=False, help="Whether to load pre-trained target model")
	parser.add_argument('--load_shadow_models', action='store_true', default=False, help="Whether to load pre-trained shadow models")
	# 無くて良い
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
		if (not args.load_target_model) and (not args.load_shadow_models) and (not args.load_attack_models):
			print("Error: No model to load. Please specify the model to load.")
			return

	# 保存ディレクトリパス作成
	timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
	if args.notes != "":
		timestamp = timestamp + "_" + args.notes
	MODEL_SAVE_DIR = os.path.join(config.MODEL_DIR, timestamp)
	# 保存ディレクトリの作成
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
	# データセットの準備 攻撃方法の選択
	# ----------------------------------
	logger.info("[Phase 1] Preparing data and selecting attack method...")
	p1_start_time = time.time()
	if is_assigned_model_path:
		dataset_instance = dataset(MODEL_SAVE_DIR, assigned_model_path=assigned_model_path)
	else:
		dataset_instance = dataset(MODEL_SAVE_DIR)
	
	# 攻撃方法の選択
	mia_method = config.MIA_METHOD
	logger.info(f"Selected MIA method: {mia_method.value}")
	if mia_method == config.mia_method.OFFLINE_LIRA:
		mia_class = MIA_LIRA(dataset_instance, MODEL_SAVE_DIR, logger)
	elif mia_method == config.mia_method.SHOKRI:
		mia_class = MIA_Shokri(dataset_instance, MODEL_SAVE_DIR, logger)
	else:
		logger.error(f"Invalid MIA method: {mia_method}")
		return

	logger.info(f"-> {time.time() - p1_start_time:.2f} sec: {((time.time() - p1_start_time) / 60):.2f} min")
	# ----------------------------------
	# ターゲットモデルの訓練と評価
	# ----------------------------------
	logger.info("[Phase 2] Training target model...")
	p2_start_time = time.time()
	target_model = TargetCNN().to(config.DEVICE)
	if not args.load_target_model:
		target_model = mia_class.train_target_model(target_model)
	else:
		target_model.load_state_dict(torch.load(os.path.join(assigned_model_path, config.TARGET_MODEL_NAME), map_location=config.DEVICE))
		logger.info("Loading complete")
	logger.info(f"-> {time.time() - p2_start_time:.2f} sec: {((time.time() - p2_start_time) / 60):.2f} min")
 
	# ----------------------------------
	# シャドーモデルの訓練と評価
	# ----------------------------------
	logger.info(f"[Phase 3] Training shadow models...")
	p3_start_time = time.time()
	shadow_models = []
	if not args.load_shadow_models:
		shadow_models = mia_class.train_shadow_models(lambda: TargetCNN())
	else:
		state_dicts = torch.load(os.path.join(assigned_model_path, config.SHADOW_MODEL_NAME), map_location=config.DEVICE)
		for i in range(config.NUM_SHADOW_MODELS):
			shadow_model = TargetCNN().to(config.DEVICE)
			shadow_model.load_state_dict(state_dicts[i])
			shadow_models.append(shadow_model)
		logger.info("Loading complete")
	logger.info(f"-> {time.time() - p3_start_time:.2f} sec: {((time.time() - p3_start_time) / 60):.2f} min")
  
	# ----------------------------------
	# 攻撃と評価
	# ----------------------------------
	logger.info("[Phase 4] Attacking and evaluating...")
	p4_start_time = time.time()
	member_trues, member_scores = mia_class.attack(shadow_models, target_model)
	logger.info(f"-> {time.time() - p4_start_time:.2f} sec: {((time.time() - p4_start_time) / 60):.2f} min")

	# ----------------------------------
	# 総合評価
	# ----------------------------------
	logger.info("[Phase 5] Comprehensive evaluation...")
	p5_start_time = time.time()
	mia_class.comprehensive_evaluate(member_trues, member_scores)
	logger.info(f"-> {time.time() - p5_start_time:.2f} sec: {((time.time() - p5_start_time) / 60):.2f} min")

	# 終了メッセージ
	logger.info("All phases completed successfully!")
	logger.info(f"Total time: {time.time() - p1_start_time:.2f} sec: {((time.time() - p1_start_time) / 60):.2f} min: {((time.time() - p1_start_time) / 3600):.2f} hr")

if __name__ == "__main__":
	main()