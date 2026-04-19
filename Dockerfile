# ベースはlatestのままでOK
FROM pytorch/pytorch:latest

ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

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

CMD ["bash"]
