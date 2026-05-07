import sys
import os
from datetime import datetime
import uuid

# config.py を読み込むためのおまじない
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import src.core.config as cfg

from celery import Celery

# 中央側はCeleryアプリのインスタンスを作るだけ
app = Celery('mia_tasks', broker=cfg.REDIS_URL)

def main():
    print("Celeryにテストタスクを送信します...")
    
    # 中央で一意な名前を生成
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # テスト用パラメータ
    params = {
        "experiment_name": timestamp,
        "mia_method": "Offline LiRA",
        "notes": "test",
        "max_epochs": 2,          # テストなので早く終わるよう少なく
        "num_shadow_models": 2,   # テストなので早く終わるよう少なく
        "target_train_size": 10520,
        "target_test_size": 10520,
        "shadow_train_size": 10520,
        "shadow_test_size": 10520
    }
    
    # delay() ではなく send_task を使う（ワーカーの関数をインポート不要）
    result = app.send_task('mia_tasks.run_attack', args=[params])
    
    print(f"タスク送信完了! Task ID: {result.id}")
    print(f"完了後、MinIOの exp/{timestamp}_test/ を確認してください。")

if __name__ == "__main__":
    main()
