# celery_tasks.py の推奨例
from celery import Celery
import tempfile
import shutil
import os


from config import ExperimentConfig, MIAMethod
import config as cfg
from pipeline import run_experiment
# import minio_utils (Phase3で作るMinIOアップロード用モジュール)

app = Celery('mia_tasks', broker=cfg.REDIS_URL)

@app.task(name='mia_tasks.run_attack')
def execute_attack_task(params_json):
    """
    params_json: {"mia_method": "Shokri", "batch_size": 128, ...} のような辞書
    """
    # JSONからConfigオブジェクトを復元 指定されていない場合はデフォルト値が使用される
    config = ExperimentConfig(**params_json)
    
    # # 2. 他のPCのNASと衝突しないよう、一時ディレクトリを生成 (例: /tmp/task_abcd1234)
    # with tempfile.TemporaryDirectory(prefix="ito_research_") as temp_dir:
        
    #     # 3. パイプライン実行 (結果は temp_dir に保存される)
    #     run_experiment(config, work_dir=temp_dir)
        
    #     # 4. Phase 3以降への布石: temp_dir の中身を丸ごと MinIO にアップロード
    #     # minio_utils.upload_directory(temp_dir, bucket_name="results")
        
    #     # Tracking APIへの送信処理などもここで行う
    temp_dir = os.path.join(cfg.MODEL_DIR, "celery_test_output")
    os.makedirs(temp_dir, exist_ok=True)
    run_experiment(config, work_dir=temp_dir)
    
    
    # withブロックを抜けると temp_dir は自動的に削除（クリーンアップ）される
    return {"status": "success", "worker_id": cfg.PC_NAME}