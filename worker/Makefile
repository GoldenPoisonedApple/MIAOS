# .envファイルを読み込む
# Makeの変数として扱う
# -include: ファイルが存在しない場合はエラーとしない
-include .env
export

# 変数定義 := 即時評価, = 遅延評価(使うときに評価)
COMPOSE_DEV := -f compose.base.yaml -f compose.dev.yaml
COMPOSE_PROD := -f compose.base.yaml -f compose.prod.yaml
COMPOSE_DEPLOY_MANUAL := -f compose.base.yaml -f compose.deploy.manual.yaml

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
	docker compose $(COMPOSE_DEV) up -d --build

# 立上げ(本番)
.PHONY: prod
prod:
	docker compose $(COMPOSE_PROD) up -d --build

# コンテナに入る(開発)
.PHONY: shell
shell:
	docker compose $(COMPOSE_DEV) exec ito_research bash

# OpenAPIからPythonクライアントを生成(開発)
.PHONY: reflect-openapi
reflect-openapi:
	docker compose $(COMPOSE_DEV) exec ito_research make openapi

# check
.PHONY: check-dev
check-dev:
	docker compose $(COMPOSE_DEV) exec ito_research make check

# 停止(開発)
.PHONY: down
down:
	docker compose $(COMPOSE_DEV) down

# 停止(本番)
.PHONY: prod-down
prod-down:
	docker compose $(COMPOSE_PROD) down

# ログ(開発)
.PHONY: logs
logs:
	docker compose $(COMPOSE_DEV) logs -f

# ログ(本番)
.PHONY: prod-logs
prod-logs:
	docker compose $(COMPOSE_PROD) logs -f

# ------------------------------
# 手動デプロイ
# ------------------------------
.PHONY: deploy-manual
deploy-manual:
	IMAGE_TAG=${IMAGE_TAG:-latest} docker compose $(COMPOSE_DEPLOY_MANUAL) up -d

# ログ
.PHONY: deploy-manual-logs
deploy-manual-logs:
	docker compose $(COMPOSE_DEPLOY_MANUAL) logs -f

# ------------------------------
# コンテナ内実行
# ------------------------------
# OpenAPIからPythonクライアントを生成
# --meta none: メタデータを含めない
.PHONY: openapi
openapi:
	uv run openapi-python-client generate --path /schema/openapi.json --meta none --output-path src/server_client --overwrite

# OpenAPI(Live)
.PHONY: openapi-live
openapi-live:
	uv run openapi-python-client generate --url $(OPENAPI_URL) --meta none --output-path src/server_client --overwrite



# Celeryを起動
.PHONY: celery
celery:
	uv run celery -A src.workers.celery_tasks worker --loglevel=info -P solo


# フォーマット
.PHONY: format
format:
	uv run ruff format src

# 静的解析
.PHONY: lint
lint:
	uv run ruff check src

# CI
# --check: 修正はしない
# --frozen: uv.lockとpyproject.tomlに不整合があった場合はエラーとなる
.PHONY: check
check:
	uv run --frozen ruff format --check src
	uv run --frozen ruff check src

# 依存関係の更新(ロックファイルを最新に更新し環境に反映)
# uv lock --upgrade + uv sync --extra dev
.PHONY: sync
sync:
	uv sync --upgrade --extra dev
