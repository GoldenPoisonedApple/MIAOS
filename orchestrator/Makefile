# Makefile
# PHONY: ファイルではないという指定(ファイルは更新されていないと実行されない): 命令である

# 変数定義 := 即時評価, = 遅延評価(使うときに評価)
COMPOSE_DEV := -f compose.base.yaml -f compose.dev.yaml
COMPOSE_PROD := -f compose.base.yaml -f compose.prod.yaml
COMPOSE_DEPLOY := -f compose.base.yaml -f compose.deploy.yaml
COMPOSE_DEPLOY_LOCAL := -f compose.base.yaml -f compose.deploy.local.yaml
COMPOSE_DEPLOY_INIT := -f compose.base.yaml -f compose.deploy.init.yaml

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
	docker compose $(COMPOSE_DEV) exec db /bin/bash

# Backendコンテナに入る
.PHONY: backshell
backshell:
	docker compose $(COMPOSE_DEV) exec backend /bin/bash

# Frontendコンテナに入る
.PHONY: frontshell
frontshell:
	docker compose $(COMPOSE_DEV) exec frontend /bin/bash

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
	docker compose $(COMPOSE_DEV) exec backend make generate-openapi

# フロントエンドでOpenAPIを使用
.PHONY: reflect-openapi
reflect-openapi:
	docker compose $(COMPOSE_DEV) exec frontend make openapi


# --------------------------------
# Check
# --------------------------------
.PHONY: check
check:
	docker compose $(COMPOSE_DEV) exec backend make check
	docker compose $(COMPOSE_DEV) exec frontend make check

# ------------------------------
# 手動デプロイ
# ------------------------------
.PHONY: deploy-local
deploy-local:
	IMAGE_TAG=${IMAGE_TAG:-latest} docker compose $(COMPOSE_DEPLOY_LOCAL) up -d

# ログ
.PHONY: deploy-local-logs
deploy-local-logs:
	docker compose $(COMPOSE_DEPLOY_LOCAL) logs -f


# ------------------------------
# 初期化
# ------------------------------
# frontendとbackendはデプロイで来るので行わない
.PHONY: deploy-init
deploy-init:
	docker compose $(COMPOSE_DEPLOY_INIT) --profile infra up -d --wait --wait-timeout 120
	docker compose $(COMPOSE_DEPLOY_INIT) --profile init run --rm create_buckets