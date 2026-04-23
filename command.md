# ビルド
docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t mia-cifar-cu130 .

# 実行
docker run --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace mia-cifar-cu130