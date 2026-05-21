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


# ファイルの所有者を変更
.PHONY: chown
chown:
	sudo chown -R $(shell whoami):$(shell whoami) .

# ------------------------------
# コンテナ管理
# ------------------------------
# 立上げ(開発)
.PHONY: dev
dev:
	docker compose -f compose.base.yaml -f compose.dev.yaml up -d --build

# 立上げ(本番)
.PHONY: prod
prod:
	docker compose -f compose.base.yaml -f compose.prod.yaml up -d --build

# コンテナに入る(開発)
.PHONY: shell
shell:
	docker compose -f compose.base.yaml -f compose.dev.yaml exec ito_research bash

# OpenAPIからPythonクライアントを生成(開発)
.PHONY: reflect-openapi
reflect-openapi:
	docker compose -f compose.base.yaml -f compose.dev.yaml exec ito_research make openapi

# 停止(開発)
.PHONY: down
down:
	docker compose -f compose.base.yaml -f compose.dev.yaml down

# 停止(本番)
.PHONY: prod-down
prod-down:
	docker compose -f compose.base.yaml -f compose.prod.yaml down

# ログ(開発)
.PHONY: logs
logs:
	docker compose -f compose.base.yaml -f compose.dev.yaml logs -f

# ログ(本番)
.PHONY: prod-logs
prod-logs:
	docker compose -f compose.base.yaml -f compose.prod.yaml logs -f

# ------------------------------
# コンテナ内実行
# ------------------------------
# OpenAPIからPythonクライアントを生成
.PHONY: openapi
openapi:
	openapi-python-client generate --url $(OPENAPI_URL) --meta none --output-path src/server_client --overwrite

# Celeryを起動
.PHONY: celery
celery:
	celery -A src.workers.celery_tasks worker --loglevel=info -P solo


# フォーマット
.PHONY: format
format:
	ruff format src

# 静的解析
.PHONY: lint
lint:
	ruff check src

# チェック
.PHONY: check
check:
	ruff check src
