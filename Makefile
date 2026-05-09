# Makefile
# PHONY: ファイルではないという指定(ファイルは更新されていないと実行されない): 命令である
.PHONY: dev prod down logs

# ------------------------------
# コンテナ管理
# ------------------------------

# 開発モードで起動
dev:
	docker compose up -d --build

# 停止(開発)
down:
	docker compose down

# ログ監視(開発)
logs:
	docker compose logs -f

# ------------------------------
# コンテナ内シェル
# ------------------------------

# docker compose execが要求するのはコンテナ名ではなくサービス名
# DBコンテナに入る
dbshell:
	docker compose exec db /bin/sh

# Backendコンテナに入る
backshell:
	docker compose exec backend /bin/sh

# Frontendコンテナに入る
frontshell:
	docker compose exec frontend /bin/sh

# redisコンテナに入る
redisshell:
	docker compose exec redis /bin/sh


# ------------------------------
# Migration
# ------------------------------
# マイグレーションファイルの作成
# 使用法: make migrate-add NAME=create_users_table
migrate-add:
	docker compose exec backend sqlx migrate add -r $(NAME)

# マイグレーションの適用
migrate:
	docker compose exec backend sqlx migrate run

# マイグレーションの取り消し
migrate-revert:
	docker compose exec backend sqlx migrate revert

# マイグレーション状態の確認
migrate-info:
	docker compose exec backend sqlx migrate info