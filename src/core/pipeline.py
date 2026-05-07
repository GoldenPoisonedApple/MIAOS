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

from src.core.config import ExperimentConfig, MIAMethod
import src.core.config as cfg
from src.data.dataset import dataset
from src.models.target_model import TargetCNN
from src.attacks.mia_lira import MIA_LIRA
from src.attacks.mia_shokri import MIA_Shokri

def run_experiment(config: ExperimentConfig, work_dir: str):
	is_assigned_model_path = (config.assigned_model_path != "")

	# シード値の設定
	torch.manual_seed(config.seed)
	if torch.cuda.is_available():
		torch.cuda.manual_seed_all(config.seed)
  
	# パス整形
	assigned_model_path = config.assigned_model_path.strip() # パスの前後の空白を削除
	# 早期終了判定
	if is_assigned_model_path:
		# 指定されたパスのディレクトリが存在しない場合早期終了
		if not os.path.exists(assigned_model_path):
			print(f"Error: Assigned model path '{assigned_model_path}' does not exist.")
			return
		# パスを指定しているのにモデルを読み込まない場合早期終了
		if (not config.load_target_model) and (not config.load_shadow_models) and (not config.load_attack_models):
			print("Error: No model to load. Please specify the model to load.")
			return
 
	# ロガー
	log_file_path = os.path.join(work_dir, "execution.log")
	logging.basicConfig(
		level=logging.INFO,
		format='%(asctime)s [%(levelname)s] %(message)s',
		handlers=[
			logging.FileHandler(log_file_path), # ファイルへの出力
			logging.StreamHandler(sys.stdout)   # 標準出力(ターミナル)への出力
		]
	)
	logger = logging.getLogger(__name__)
 
	# メタ情報表示
	logger.info("Configurations:")
	for key, value in vars(config).items():
		if not key.startswith("_"): # アンダースコアから始まるものは非表示
			logger.info(f"  {key}: {value}")


	# ----------------------------------
	# データセットの準備 攻撃方法の選択
	# ----------------------------------
	logger.info("[Phase 1] Preparing data and selecting attack method...")
	p1_start_time = time.time()
	if is_assigned_model_path:
		dataset_instance = dataset(work_dir, config, assigned_model_path=assigned_model_path)
	else:
		dataset_instance = dataset(work_dir, config)
	
	# 攻撃方法の選択
	mia_method = config.mia_method
	logger.info(f"Selected MIA method: {mia_method.value}")
	if mia_method == MIAMethod.OFFLINE_LIRA:
		mia_class = MIA_LIRA(dataset_instance, work_dir, logger, config)
	elif mia_method == MIAMethod.SHOKRI:
		mia_class = MIA_Shokri(dataset_instance, work_dir, logger, config)
	else:
		logger.error(f"Invalid MIA method: {mia_method}")
		return

	logger.info(f"-> {time.time() - p1_start_time:.2f} sec: {((time.time() - p1_start_time) / 60):.2f} min")
	# ----------------------------------
	# ターゲットモデルの訓練と評価
	# ----------------------------------
	logger.info("[Phase 2] Training target model...")
	p2_start_time = time.time()
	target_model = TargetCNN().to(cfg.DEVICE)
	if not config.load_target_model:
		target_model = mia_class.train_target_model(target_model)
	else:
		target_model.load_state_dict(torch.load(os.path.join(assigned_model_path, cfg.TARGET_MODEL_NAME), map_location=cfg.DEVICE))
		logger.info("Loading complete")
	logger.info(f"-> {time.time() - p2_start_time:.2f} sec: {((time.time() - p2_start_time) / 60):.2f} min")
 
	# ----------------------------------
	# シャドーモデルの訓練と評価
	# ----------------------------------
	logger.info(f"[Phase 3] Training shadow models...")
	p3_start_time = time.time()
	shadow_models = []
	if not config.load_shadow_models:
		shadow_models = mia_class.train_shadow_models(lambda: TargetCNN())
	else:
		state_dicts = torch.load(os.path.join(assigned_model_path, cfg.SHADOW_MODEL_NAME), map_location=cfg.DEVICE)
		for i in range(config.num_shadow_models):
			shadow_model = TargetCNN().to(cfg.DEVICE)
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
