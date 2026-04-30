# ベースはlatestのままでOK
FROM python:3.10-slim

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

# タイムゾーンと基本パッケージの設定
RUN apt-get update && apt-get install -y --no-install-recommends tzdata build-essential \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# --- ユーザー作成の追加 ---
ARG UID=1000
ARG GID=1000
ARG USERNAME=tipsy

RUN if ! getent group ${GID} > /dev/null 2>&1; then \
        groupadd -g ${GID} ${USERNAME}; \
    fi && useradd -u ${UID} -g ${GID} -m -s /bin/bash ${USERNAME}

WORKDIR /workspace

# PyTorch CUDA 13.0
RUN pip install --pre --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu130 --no-cache-dir

# その他の依存パッケージ
RUN pip install --no-cache-dir \
    numpy \
    scikit-learn \
    matplotlib \
    tqdm \
    pandas \
    jupyterlab

ENV TORCH_HOME=/workspace/.cache/torch

USER ${USERNAME}

CMD ["bash"]
