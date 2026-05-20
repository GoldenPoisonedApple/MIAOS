# Makefile
# PHONY: ファイルではないという指定(ファイルは更新されていないと実行されない): 命令である

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

# 開発モードで起動
.PHONY: dev
dev:
	docker compose up -d --build

# 停止(開発)
.PHONY: down
down:
	docker compose down

# ログ監視(開発)
.PHONY: logs
logs:
	docker compose logs -f

# ------------------------------
# コンテナ内シェル
# ------------------------------

# docker compose execが要求するのはコンテナ名ではなくサービス名
# DBコンテナに入る
.PHONY: dbshell
dbshell:
	docker compose exec db /bin/sh

# Backendコンテナに入る
.PHONY: backshell
backshell:
	docker compose exec backend /bin/sh

# Frontendコンテナに入る
.PHONY: frontshell
frontshell:
	docker compose exec frontend /bin/sh

# redisコンテナに入る
.PHONY: redisshell
redisshell:
	docker compose exec redis /bin/sh

# ------------------------------
# OpenAPI
# ------------------------------
# JSONファイル生成
.PHONY: generate-openapi
generate-openapi:
	docker compose exec backend cargo run --bin generate_openapi > ../schema/openapi.json

# フロントエンドでOpenAPIを使用
.PHONY: reflect-openapi
reflect-openapi:
	docker compose exec frontend make openapi
