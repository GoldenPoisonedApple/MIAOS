from celery_tasks import execute_attack_task

def main():
    print("Celeryにテストタスクを送信します...")
    
    # テスト用パラメータ
    params = {
        "mia_method": "Offline LiRA",
        "notes": "test",
        "max_epochs": 10,
        "num_shadow_models": 10,
        "target_train_size": 10520,
        "target_test_size": 10520,
        "shadow_train_size": 10520,
        "shadow_test_size": 10520
    }
    
    # delay()メソッドでRedisキューにタスクを入れる
    result = execute_attack_task.delay(params)
    
    print(f"タスク送信完了! Task ID: {result.id}")
    print("ワーカー側のターミナルで処理が開始されるか確認してください。")

if __name__ == "__main__":
    main()