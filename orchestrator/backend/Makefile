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