import os
import torch
from enum import Enum

# ワーカーのPC名
PC_NAME: str = os.environ["PC_NAME"]
# RedisのURL
_REDIS_URL: str = os.environ["REDIS_URL"]
# MinIOのURL
_MINIO_URL: str = os.environ["MINIO_URL"]
# MinIOのアクセスキー
_MINIO_ACCESS_KEY: str = os.environ["MINIO_ACCESS_KEY"]
# MinIOのシークレットキー
_MINIO_SECRET_KEY: str = os.environ["MINIO_SECRET_KEY"]
# MinIOのバケット名
_MINIO_BUCKET_NAME: str = os.environ["MINIO_BUCKET_NAME"]
# MIAOS APIのURL
_MIAOS_API_URL: str = os.environ["MIAOS_API_URL"]
# デバイス
DEVICE: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# データセットの保存先ディレクトリ
DATA_DIR: str = "./data"
# モデルの保存先ディレクトリ
MODEL_DIR: str = "./models"
# キャッシュ
LOCAL_CACHE_DIR: str = "./cache"
# ターゲットモデルの保存名
TARGET_MODEL_NAME: str = "target_model.pth"
# シャドーモデルの保存名
SHADOW_MODEL_NAME: str = "shadow_models.pth"
# 攻撃モデルの保存名
ATTACK_MODEL_NAME: str = "attack_models.pth"

# クラスの数
NUM_CLASSES: int = 100
# 攻撃モデルのエポック数
ATTACK_MODEL_EPOCHS: int = 10

# workerタイムアウト時間(秒) 1時間
CELERY_VISIBILITY_TIMEOUT: int = 60 * 60 * 1


# 攻撃手法の列挙型
class MIAMethod(Enum):
    OFFLINE_LIRA = "Offline LiRA"
    SHOKRI = "Shokri"
