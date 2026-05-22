# Makefile
# PHONY: ファイルではないという指定(ファイルは更新されていないと実行されない): 命令である

# 変数定義 := 即時評価, = 遅延評価(使うときに評価)
COMPOSE_DEV := -f compose.base.yaml -f compose.dev.yaml
COMPOSE_PROD := -f compose.base.yaml -f compose.prod.yaml
COMPOSE_DEPLOY := -f compose.base.yaml -f compose.deploy.yaml
COMPOSE_DEPLOY_MANUAL := -f compose.base.yaml -f compose.deploy.manual.yaml

# ------------------------------
# コンテナ管理
# ------------------------------
# ファイルの所有者を変更
.PHONY: chown
chown:
	sudo chown -R $(shell whoami):$(shell whoami) .

# メモ
# バックエンドだけ再起動
# docker compose up -d --build backend

# 起動(開発)
.PHONY: dev
dev:
	docker compose $(COMPOSE_DEV) up -d --build

# 起動(本番)
.PHONY: prod
prod:
	docker compose $(COMPOSE_PROD) up -d --build

# 停止(開発)
.PHONY: down
down:
	docker compose $(COMPOSE_DEV) down

# 停止(本番)
.PHONY: prod-down
prod-down:
	docker compose $(COMPOSE_PROD) down

# ログ監視(開発)
.PHONY: logs
logs:
	docker compose $(COMPOSE_DEV) logs -f

# ログ監視(本番)
.PHONY: prod-logs
prod-logs:
	docker compose $(COMPOSE_PROD) logs -f

# ------------------------------
# コンテナ内シェル
# ------------------------------

# docker compose execが要求するのはコンテナ名ではなくサービス名
# DBコンテナに入る
.PHONY: dbshell
dbshell:
	docker compose $(COMPOSE_DEV) exec db /bin/sh

# Backendコンテナに入る
.PHONY: backshell
backshell:
	docker compose $(COMPOSE_DEV) exec backend /bin/sh

# Frontendコンテナに入る
.PHONY: frontshell
frontshell:
	docker compose $(COMPOSE_DEV) exec frontend /bin/sh

# redisコンテナに入る
.PHONY: redisshell
redisshell:
	docker compose $(COMPOSE_DEV) exec redis /bin/sh

# ------------------------------
# OpenAPI
# ------------------------------
# JSONファイル生成
.PHONY: generate-openapi
generate-openapi:
	docker compose $(COMPOSE_DEV) exec backend cargo run --bin generate_openapi > ../schema/openapi.json

# フロントエンドでOpenAPIを使用
.PHONY: reflect-openapi
reflect-openapi:
	docker compose $(COMPOSE_DEV) exec frontend make openapi


# ------------------------------
# 手動デプロイ
# ------------------------------
# --no-deps: 依存サービスは再起動しない
# --remove-orphans: 不要なコンテナを削除
.PHONY: deploy-manual
deploy-manual:
	IMAGE_TAG=${IMAGE_TAG:-latest} docker compose $(COMPOSE_DEPLOY_MANUAL) up -d