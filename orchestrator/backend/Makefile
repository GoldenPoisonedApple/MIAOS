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