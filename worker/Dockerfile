# ---------------------------------
# Base Stage: 開発・本番の共通のイメージ
# ---------------------------------
# NVIDIA NGCコンテナの利用 (マルチアーキテクチャ対応済みのタグを指定)
# 状況に応じてホストのドライババージョンに適合するタグに変更してください
FROM nvcr.io/nvidia/pytorch:26.03-py3 AS base
WORKDIR /workspace

# apt-get等の対話型プロンプトによるビルド停止を防止
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

# Ubuntuベースの場合、tzdataの明示的なインストールを推奨
RUN apt-get update && apt-get install -y --no-install-recommends \
	tzdata \
	&& ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
	&& echo $TZ > /etc/timezone \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

# [修正点]
# NGCコンテナには最適化済みのPyTorchが含まれているため、pytorchのインストールは不要

# その他の依存パッケージのインストール
# 本当はpipもバージョン固定した方がいいんだとは思う requirements.txtとか
RUN pip install --no-cache-dir --upgrade pip \
	&& pip install --no-cache-dir \
	numpy \
	scikit-learn \
	matplotlib \
	tqdm \
	pandas \
	celery \
	redis \
	minio \
	boto3 \
	requests \
	python-dotenv

ENV TORCH_HOME=/workspace/.cache/torch


# ---------------------------------
# Development Stage: 開発用イメージ
# ---------------------------------
FROM base AS dev
WORKDIR /workspace

# 開発に必要なツールのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
	curl \
	git \
	make \
	&& rm -rf /var/lib/apt/lists/*

# 依存関係のインストール
RUN pip install --no-cache-dir --upgrade pip \
	&& pip install --no-cache-dir \
	jupyterlab \
	openapi-python-client \
	ruff

CMD ["bash"]

# ---------------------------------
# Production Stage: 本番用イメージ
# ---------------------------------
FROM base AS prod
WORKDIR /workspace

# 非rootユーザー作成
# TORCH_HOMEのためディレクトリ作成
RUN useradd -ms /bin/bash appuser \
	&& mkdir -p /workspace/.cache/torch \
	&& chown -R appuser:appuser /workspace

# ソースコードをコピー
COPY --chown=appuser:appuser src/ /workspace/src/

# 実行ユーザーを切り替え
USER appuser

CMD ["celery", "-A", "src.workers.celery_tasks", "worker", "--loglevel=info", "-P", "solo"]