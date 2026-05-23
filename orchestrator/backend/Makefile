# ------------------------------
# フォーマットと静的解析
# ------------------------------
# フォーマット
.PHONY : format
format:
	cargo fmt --all

# 静的解析
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
	cargo test -- --test-threads=1

# CI
.PHONY: ci
ci:
	cargo fmt --all -- --check
	cargo clippy --all-targets --all-features -- -D warnings

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