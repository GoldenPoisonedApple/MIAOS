# .envファイルを読み込む
# Makeの変数として扱う
include .env
export

# こういうやり方もある: Shellスクリプト(自由度が高い)
# 例
# openapi:
# 	set -a; \
# 	source .env; \
# 	set +a; \
# 	openapi-python-client generate --url $$OPENAPI_URL --meta none --output-path src/server_client --overwrite
# set -a: 自動で環境変数に展開(exportを自動付与)
# source .env: .envファイルを読み込む, source: ファイルの中身を現在のシェルでそのまま実行する, set -a環境のため環境変数になる
# set +a: 環境変数の展開を終了
# 一行にしないと、各行別のシェルのため意味がない


# OpenAPIからPythonクライアントを生成
.PHONY: openapi
openapi:
	openapi-python-client generate --url $(OPENAPI_URL) --meta none --output-path src/server_client --overwrite

# ビルド
.PHONY: build
build:
	docker build -t mia_ito .

# 開発用立上げ
.PHONY: dev
dev:
	docker run -d --gpus all --name ito_research -it --shm-size=8g -v $(CURDIR):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito

# コンテナに入る
.PHONY: shell
shell:
	docker exec -it ito_research bash

# 実行
.PHONY: run
run:
	docker run -d --gpus all --name ito_research -it --rm --shm-size=8g -v $(CURDIR):/workspace -e PYTHONPATH=/workspace --env-file .env mia_ito bash -c "celery -A src.workers.celery_tasks worker --loglevel=info -P solo"

# コンテナ内実行
.PHONY: celery
celery:
	celery -A src.workers.celery_tasks worker --loglevel=info -P solo

# コンテナを停止・削除
.PHONY: remove
remove:
	docker stop ito_research
	docker rm ito_research

# ファイルの所有者を変更
.PHONY: chown
chown:
	sudo chown -R $(shell whoami):$(shell whoami) .

# ログ
# docker logs -f <container_id>

# 保存場所の指定 読み込みは同じ、出力は特定場所
# docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace:ro -v /tmp/mia_ito:/workspace/models mia_ito python main.py
