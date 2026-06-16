# ------------------------------
# フォーマットと静的解析
# ------------------------------
# フォーマット
.PHONY : format
format:
	cargo fmt --all

# 静的解析
# -D warnings: 警告もエラー扱い
.PHONY : lint
lint:
	cargo clippy --all-targets --all-features -- -D warnings

# 自動修正
.PHONY : lint-fix
lint-fix:
	cargo clippy --all-targets --all-features --fix --allow-dirty --allow-no-vcs

# テスト
.PHONY : test
test:
	cargo test

# 統合テスト
# --test-threads=1: 外部依存があるのでテストを並列実行しない
.PHONY : test-integration
test-integration:
	cargo test --all-features -- --test-threads=1


# ------------------------------
# Migration
# ------------------------------
# マイグレーションファイルの作成
# 使用法: make migrate-add NAME=create_users_table
migrate-add:
	sqlx migrate add -r $(NAME)

# マイグレーションの適用
migrate:
	sqlx migrate run

# マイグレーションの取り消し
migrate-revert:
	sqlx migrate revert

# マイグレーション状態の確認
migrate-info:
	sqlx migrate info


# ------------------------------
# OpenAPI
# ------------------------------
# JSONファイル生成
.PHONY: generate-openapi
generate-openapi:
	cargo run --bin generate_openapi > /schema/openapi.json

# --------------------------------
# CI
# --------------------------------
.PHONY: check
check:
	${MAKE} migrate
	cargo fmt --all -- --check
	${MAKE} lint
	${MAKE} test-integration