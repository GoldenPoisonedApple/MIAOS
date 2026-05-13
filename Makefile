# OpenAPIからPythonクライアントを生成
.PHONY: openapi
openapi:
	openapi-python-client generate --url http://ksl-v03.nagaokaut.ac.jp:3000/api-docs/openapi.json --meta none --output-path src/server_client --overwrite

# ビルド
.PHONY: build
build:
	docker build -t mia_ito .

# 開発用立上げ
.PHONY: dev
dev:
	docker run -d --gpus all -it --shm-size=8g -v $(pwd):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito

# 実行
.PHONY: run
run:
	docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito bash -c "celery -A src.workers.celery_tasks worker --loglevel=info -P solo"
