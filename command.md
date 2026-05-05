# ビルド
docker build -t mia_ito .
# ビルド(arm64)
docker build -f Dockerfile.arm64 -t mia_ito .


# 実行
docker run --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace mia_ito


# バックグラウンド実行
docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace mia_ito python main.py
# 保存場所の指定 読み込みは同じ、出力は特定場所
docker run -d --gpus all -it --rm --shm-size=8g -v $(pwd):/workspace:ro -v /tmp/mia_ito:/workspace/models mia_ito python main.py

# ログ
docker logs -f <container_id>


# 読み込みの例
python main.py --assigned_model_path "2026-04-24_19-03_all" --load_target_model --load_attack_dataset --load_attack_models