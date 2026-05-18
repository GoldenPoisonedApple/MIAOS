# ---------------------------------
# Base Stage: 開発・本番の共通のイメージ
# ---------------------------------
	FROM rust:1.93-slim-bookworm AS base
	WORKDIR /app
	
	# 必要なシステムパッケージのインストール
	# - pkg-config, libssl-dev: Rustのコンパイルに必要
	# - lld, clang: 高速なリンカー(任意だが推奨)
	RUN apt-get update && apt-get install -y \
		pkg-config \
		libssl-dev \
		lld \
		clang \
		&& rm -rf /var/lib/apt/lists/*
	
	# cargo-chef: ビルドキャッシュ最適化用
	RUN cargo install --locked cargo-chef
	
	# ---------------------------------------------------
	# Planner Stage: 依存関係計算
	# ---------------------------------------------------
	FROM base AS planner
	# ソースコードコピー
	COPY . .
	# 依存関係の情報のみ抽出: recipe.json
	RUN cargo chef prepare --recipe-path recipe.json
	
	
	# ---------------------------------
	# Development Stage: 開発用イメージ
	# ---------------------------------
	FROM base AS dev
	WORKDIR /app
	
	# 開発に必要なツールのインストール
	RUN apt-get update && apt-get install -y \
		curl \
		git \
		make \
		&& rm -rf /var/lib/apt/lists/*

	# 環境変数の設定 なぜかこれしないとcargoが使えない
	ENV PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:${PATH}"

	RUN rustup component add rustfmt

	
	# SQLx CLI: データベースマイグレーション用
	RUN cargo install --locked sqlx-cli --no-default-features --features postgres
	# cargo-watch: ホットリロード用
	RUN cargo install --locked cargo-watch
	
	# 依存関係取得
	COPY --from=planner /app/recipe.json recipe.json
	# ローカルの依存クレートコピー
	COPY libs ./libs
	# 依存関係ビルド
	RUN cargo chef cook --recipe-path recipe.json
	
	# ポート公開
	EXPOSE 3000
	
	# ソースコードはホストからバインドマウントすることを想定
	# ホットリロードで起動
	CMD ["cargo", "watch", "-x", "run"]	
	
	# ---------------------------------------------------
	# Builder Stage: 本番用ビルド
	# ---------------------------------------------------
	FROM base AS builder
	
	# 依存関係取得
	COPY --from=planner /app/recipe.json recipe.json
	# ローカルの依存クレートコピー
	COPY libs ./libs
	# 依存関係のみをビルド: 本番用
	RUN cargo chef cook --release --recipe-path recipe.json
	
	# ソースコードコピー
	COPY . .
	# 本番ビルド
	RUN cargo build --release
	
	
	# ---------------------------------
	# Production Stage: 本番用イメージ
	# ---------------------------------
	FROM debian:bookworm-slim AS prod
	WORKDIR /app
	
	# 実行時に必要な SSL ライブラリ等のみインストール
	RUN apt-get update && apt-get install -y \
		ca-certificates \
		libssl3 \
		&& rm -rf /var/lib/apt/lists/*
	
	# 非rootユーザー作成
	RUN useradd -m appuser
	
	# ビルドステージからバイナリだけをコピー
	COPY --chown=appuser:appuser --from=builder /app/target/release/server /usr/local/bin/server
	
	# 実行ユーザーを切り替え
	USER appuser
	
	# ポート公開
	EXPOSE 3000
	
	CMD ["server"]