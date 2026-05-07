# celery_tasks.py の推奨例
from celery import Celery
import tempfile
import shutil
import os


from src.core.config import ExperimentConfig, MIAMethod
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
        run_experiment(config, work_dir=temp_dir)
        
        # 実行結果アップロード
        minio_utils.upload_results_dir(temp_dir, remote_prefix=f"exp/{config.experiment_name}_{config.notes}")
        
    
    
    # withブロックを抜けると temp_dir は自動的に削除（クリーンアップ）される
    return {"status": "success", "worker_id": cfg.PC_NAME}