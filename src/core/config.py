import os
import torch
from enum import Enum
from dotenv import load_dotenv

load_dotenv()
# ワーカーのPC名
PC_NAME: str = os.getenv("PC_NAME")
# RedisのURL
REDIS_URL: str = os.getenv("REDIS_URL")
# MinIOのURL
MINIO_URL: str = os.getenv("MINIO_URL")
# MinIOのアクセスキー
MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY")
# MinIOのシークレットキー
MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY")
# MinIOのバケット名
MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME")
# Tracking APIのURL
MIAOS_API_URL: str = os.getenv("MIAOS_API_URL")

# デバイス
DEVICE: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# データセットの保存先ディレクトリ
DATA_DIR: str = './data'
# モデルの保存先ディレクトリ
MODEL_DIR: str = './models'
# キャッシュ
LOCAL_CACHE_DIR: str = './cache'
# ターゲットモデルの保存名
TARGET_MODEL_NAME: str = 'target_model.pth'	
# シャドーモデルの保存名
SHADOW_MODEL_NAME: str = 'shadow_models.pth'
# 攻撃モデルの保存名
ATTACK_MODEL_NAME: str = 'attack_models.pth'

# クラスの数
NUM_CLASSES: int = 100
# 攻撃モデルのエポック数
ATTACK_MODEL_EPOCHS: int = 10

# 攻撃手法の列挙型
class MIAMethod(Enum):
	OFFLINE_LIRA = "Offline LiRA"
	SHOKRI = "Shokri"
