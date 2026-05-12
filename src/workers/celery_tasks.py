# celery_tasks.py の推奨例
from celery import Celery
import tempfile
import time
import requests
from dataclasses import asdict
import os

from src.core.config import ExperimentConfig
import src.core.config as cfg
from src.core.pipeline import run_experiment
import src.utils.minio_utils as minio_utils

app = Celery('mia_tasks', broker=cfg.REDIS_URL)

@app.task(name='mia_tasks.run_attack')
def execute_attack_task(params_json):
	"""
	params_json: {"mia_method": "Shokri", "batch_size": 128, ...} のような辞書
	"""
	# JSONからConfigオブジェクトを復元 指定されていない場合はデフォルト値が使用される
	config = ExperimentConfig(**params_json)
	
	# 依存モデルが存在する場合
	if config.assigned_model_path != "":
		# ダウンロード
		# MinIOから落としてきたローカルの絶対パスを取得し、設定を上書きする
		local_model_path = minio_utils.download_model_dir(config.assigned_model_path)
		config.assigned_model_path = local_model_path

	
	# 他のPCのNASと衝突しないよう、一時ディレクトリを生成
	# ここにおける一時ディレクトリはコンテナ内の /tmp/ 配下に作成される
	with tempfile.TemporaryDirectory(prefix="ito_research_") as temp_dir:
		
		# パイプライン実行 (結果は temp_dir に保存される)
		metrics = run_experiment(config, work_dir=temp_dir)
		
		# OSのファイルシステム同期を確実に行うための待機
		time.sleep(2)
		
		# 実行結果アップロード
		remote_prefix = f"exp/{config.experiment_name}"
		minio_utils.upload_results_dir(temp_dir, remote_prefix=remote_prefix)
		
		# ------- Tracking APIへの送信処理 -------
		# 実行条件 辞書変換
		config_dict = asdict(config)
		config_dict["mia_method"] = config.mia_method.value # Enumを文字列に変換
		# artifacts リスト作成
		artifacts = []
		for root, _, files in os.walk(temp_dir):
			for file in files:
				# temp_dirを起点とした相対パスを計算
				rel_path = os.path.relpath(os.path.join(root, file), temp_dir)
				artifacts.append(rel_path)		
		# ペイロード作成
		payload = {
			"minio_path": remote_prefix,
			"worker_id": cfg.PC_NAME,
			"artifacts": artifacts,	# 実行結果のファイルパスリスト
			"metrics": metrics,       # 実行結果
			"parameters": config_dict # 実行条件
		}
		try:
			# RustのTracking APIへPOST送信
			api_url = cfg.TRACKING_API_URL
			response = requests.post(api_url, json=payload, timeout=10)
			response.raise_for_status() # HTTPエラーなら例外を出す
			print(f"Tracking APIへの送信成功: {response.text}")
		except Exception as e:
			# MinIOには保存できているので、タスク全体を失敗扱いにせずエラーログだけ出すのが推奨
			print(f"Tracking APIへの送信失敗: {e}")
				
	# withブロックを抜けると temp_dir は自動的に削除（クリーンアップ）される
	return {"status": "success", "worker_id": cfg.PC_NAME}