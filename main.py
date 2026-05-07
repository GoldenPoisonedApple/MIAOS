# main.py の推奨例
import argparse
from config import ExperimentConfig
import config as cfg
from pipeline import run_experiment
import os
from datetime import datetime

def main():
	# 引数をパース
	parser = argparse.ArgumentParser(description="Membership Inference Attack")
	parser.add_argument('--assigned_model_path', type=str, default="", help="Path to load pre-trained models")
	parser.add_argument('--notes', type=str, default="", help="Special notes")	
	parser.add_argument('--load_target_model', action='store_true', default=False, help="Whether to load pre-trained target model")
	parser.add_argument('--load_shadow_models', action='store_true', default=False, help="Whether to load pre-trained shadow models")
	parser.add_argument('--load_attack_models', action='store_true', default=False, help="Whether to load pre-trained attack models")
	args = parser.parse_args()

	# 保存ディレクトリの作成
	work_dir = os.path.join(cfg.MODEL_DIR, datetime.now().strftime("%Y-%m-%d_%H-%M"))
	os.makedirs(work_dir, exist_ok=True)
	# 手動実行の場合 MODEL_DIR 配下に存在するはず
	assigned_model_path = os.path.join(cfg.MODEL_DIR, args.assigned_model_path)
	# Configオブジェクトを作成
	config = ExperimentConfig(
		assigned_model_path=assigned_model_path,
		notes=args.notes,
		load_target_model=args.load_target_model,
		load_shadow_models=args.load_shadow_models,
		load_attack_models=args.load_attack_models,
	)

	# 3. パイプライン実行
	run_experiment(config, work_dir)

if __name__ == "__main__":
    main()