# ビルド
docker build -t mia_ito .


# 実行
docker run --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace --env-file .env mia_ito

# 実行
docker run --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace --env-file .env mia_ito bash -c "celery -A celery_tasks worker --loglevel=info --concurrency=1"
# バックグラウンド実行
docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace --env-file .env mia_ito bash -c "celery -A celery_tasks worker --loglevel=info --concurrency=1"

# 保存場所の指定 読み込みは同じ、出力は特定場所
# docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace:ro -v /tmp/mia_ito:/workspace/models mia_ito python main.py

# ログ
docker logs -f <container_id>
