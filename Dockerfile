# ベースはlatestのままでOK
FROM pytorch/pytorch:latest

ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# --- ユーザー作成の追加 ---
ARG UID=1000
ARG GID=1000
ARG USERNAME=devuser

RUN groupadd -g ${GID} ${USERNAME} && useradd -u ${UID} -g ${GID} -m -s /bin/bash ${USERNAME}

WORKDIR /workspace


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
