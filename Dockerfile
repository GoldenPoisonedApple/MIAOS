# NVIDIA NGCコンテナの利用 (マルチアーキテクチャ対応済みのタグを指定)
# 状況に応じてホストのドライババージョンに適合するタグに変更してください
FROM nvcr.io/nvidia/pytorch:26.03-py3

# apt-get等の対話型プロンプトによるビルド停止を防止
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

# Ubuntuベースの場合、tzdataの明示的なインストールを推奨
RUN apt-get update && apt-get install -y tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# [修正点]
# NGCコンテナには最適化済みのPyTorchが含まれているため、pipによる強制再インストールは削除。
# (ARM64向け公式Nightly Wheelは存在しないため、元のコマンドは機能しません)

# その他の依存パッケージのインストール
RUN pip install --no-cache-dir \
    numpy \
    scikit-learn \
    matplotlib \
    tqdm \
    pandas \
    jupyterlab

ENV TORCH_HOME=/workspace/.cache/torch

CMD ["bash"]