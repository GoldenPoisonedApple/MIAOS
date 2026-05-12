# celery_tasks.py の推奨例
from celery import Celery
import tempfile
import time
import os

import src.core.config as cfg
from src.core.pipeline import run_experiment
import src.utils.minio_utils as minio_utils

from src.server_client import Client
from src.server_client.models import CreateExperimentRequest, UpdateResultsRequest, UpdateResultsRequestOtherFiles, UpdateResultsRequestOtherMetrics
from src.server_client.api.experiments import reflect_experiment_results

app = Celery('mia_tasks', broker=cfg.REDIS_URL)

@app.task(name='mia_tasks.run_attack')
def execute_attack_task(_params):
	"""
	_params: {"mia_method": "Shokri", "batch_size": 128, ...} のような辞書
	"""
	# idを取得、削除
	id = _params.pop("experiment_id")
	# JSONからCreateExperimentRequestオブジェクトを復元
	request = CreateExperimentRequest.from_dict(_params)
	
	# 依存モデルが存在する場合
	if request.base_experiment_id is not None:
		# ダウンロード
		# MinIOから落としてきたローカルの絶対パスを取得し、設定を上書きする
		assigned_model_path = minio_utils.download_model_dir(request.base_experiment_id)
	else:
		assigned_model_path = None

	
	# 他のPCのNASと衝突しないよう、一時ディレクトリを生成
	# ここにおける一時ディレクトリはコンテナ内の /tmp/ 配下に作成される
	with tempfile.TemporaryDirectory(prefix="ito_research_") as temp_dir:
		
		# パイプライン実行 (結果は temp_dir に保存される)
		metrics = run_experiment(request, work_dir=temp_dir, assigned_model_path=assigned_model_path, experiment_id=id)
		
		# OSのファイルシステム同期を確実に行うための待機
		time.sleep(2)
		
		# 実行結果アップロード
		remote_prefix = f"{id}/"
		minio_utils.upload_results_dir(temp_dir, remote_prefix=remote_prefix)
		
		# ------- MIAOS APIへの送信処理 -------
		# artifacts リスト作成
		artifacts = []
		for root, _, files in os.walk(temp_dir):
			for file in files:
				# temp_dirを起点とした相対パスを計算
				rel_path = os.path.relpath(os.path.join(root, file), temp_dir)
				artifacts.append(rel_path)		
		# ペイロード作成
		payload = UpdateResultsRequest(
      		dataset_json_path=os.path.join(temp_dir, "dataset.json"),
			execution_log_path=os.path.join(temp_dir, "execution.log"),
			experiment_id=id,
			global_auc=metrics["global_auc"],
			minio_path=remote_prefix,
			other_files=UpdateResultsRequestOtherFiles(
				artifacts=artifacts
			),
			other_metrics=UpdateResultsRequestOtherMetrics(
				threshold_at_1_fpr=metrics["threshold_at_1_fpr"],
				threshold_at_01_fpr=metrics["threshold_at_01_fpr"],
				threshold_at_001_fpr=metrics["threshold_at_001_fpr"],
				tpr_at_001_fpr=metrics["tpr_at_001_fpr"],
			),
			total_time=metrics["total_time_sec"],
			tpr_at_1_fpr=metrics["tpr_at_1_fpr"],
			tpr_at_01_fpr=metrics["tpr_at_01_fpr"],
			worker_name=cfg.PC_NAME,
		)
		try:
			client = Client(base_url=cfg.MIAOS_API_URL)
			response = reflect_experiment_results.sync(client=client, body=payload)
			print(f"Tracking APIへの送信成功: {response}")
		except Exception as e:
			print(f"Tracking APIへの送信失敗: {e}")
				
	# withブロックを抜けると temp_dir は自動的に削除（クリーンアップ）される
	return {"status": "success", "worker_id": cfg.PC_NAME}