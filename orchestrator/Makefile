# Makefile
# PHONY: ファイルではないという指定(ファイルは更新されていないと実行されない): 命令である
.PHONY: dev prod down logs

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
