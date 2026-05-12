# ビルド
docker build -t mia_ito .


# 実行
docker run --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito
# 開発用実行
docker run -d --gpus all -it --shm-size=8g -v $(pwd):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito


# 実行
docker run --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito bash -c "celery -A src.workers.celery_tasks worker --loglevel=info -P solo"
# バックグラウンド実行
docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito bash -c "celery -A src.workers.celery_tasks worker --loglevel=info -P solo"

# 保存場所の指定 読み込みは同じ、出力は特定場所
# docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace:ro -v /tmp/mia_ito:/workspace/models mia_ito python main.py

# ログ
docker logs -f <container_id>


# 色々変更を加えた場合
docker stop <container_id>
docker rm <container_id>
# で、再実行

# openapi-python-client の生成
openapi-python-client generate --url http://ksl-v03.nagaokaut.ac.jp:3000/api-docs/openapi.json --meta none --output-path src/server_client
# ローカル URLから取ってこれるからいらんかったけど
openapi-python-client generate --path ./openapi.json --meta none --output-path src/server_client