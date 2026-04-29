# ビルド
docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t mia-cifar-cu130 .
# ビルド(arm64)
docker build -f Dockerfile.arm64 --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t mia-cifar-cu130 .


# 実行
docker run --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace mia-cifar-cu130


# バックグラウンド実行
docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace mia-cifar-cu130 python main.py

# ログ
docker logs -f <container_id>


# 読み込みの例
python main.py --assigned_model_path "2026-04-24_19-03_all" --load_target_model --load_attack_dataset --load_attack_models