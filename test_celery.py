from celery import Celery
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

# Celeryアプリのインスタンスだけ作る（中身は空でOK、RedisのURLだけ合っていれば通信できる）
app = Celery('mia_tasks', broker=REDIS_URL)
def main():
    print("Celeryにテストタスクを送信します...")
    
    # 中央で一意な名前を生成
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # テスト用パラメータ
    params = {
        "experiment_name": timestamp,
        "mia_method": "Offline LiRA",
        "notes": "test",
        "max_epochs": 10,
        "num_shadow_models": 10,
        "target_train_size": 10520,
        "target_test_size": 10520,
        "shadow_train_size": 10520,
        "shadow_test_size": 10520
    }    
    # execute_attack_task を import せず、タスク名を「文字列」で指定して直接Redisに投げる
    result = app.send_task('mia_tasks.run_attack', args=[params])
    
    print(f"タスク送信完了! Task ID: {result.id}, Experiment Name: {params['experiment_name']}")
if __name__ == "__main__":
    main()