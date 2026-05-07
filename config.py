import os
import torch
from enum import Enum
from dataclasses import dataclass
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

# 攻撃手法の列挙型
class MIAMethod(Enum):
	OFFLINE_LIRA = "Offline LiRA"
	SHOKRI = "Shokri"
 
@dataclass
class ExperimentConfig:
	# 実験名
	experiment_name: str = ""
	# 指定パスが存在する場合、そのパスを使用
	assigned_model_path: str = ""
	# ノート
	notes: str = ""
	# ターゲットモデルを読み込むかどうか
	load_target_model: bool = False
	# シャドーモデルを読み込むかどうか
	load_shadow_models: bool = False
	# 攻撃モデルを読み込むかどうか
	load_attack_models: bool = False
	# 攻撃手法
	mia_method: MIAMethod = MIAMethod.OFFLINE_LIRA
	# シャドーモデルの数
	num_shadow_models: int = 10
	# クラス数
	num_classes: int = 100
	# バッチサイズ
	batch_size: int = 256
	# 最大エポック数
	max_epochs: int = 20
	# 攻撃モデルのエポック数
	attack_model_epochs: int = 10
	# データロードに使用するサブプロセス数
	num_workers: int = 0
	# データセットの数
	# 各モデルの訓練データとテストデータは重複無し、同サイズ
	# → メンバと非メンバを同数にすることでBaseを50%にする
	# → ターゲットとシャドーでの数を同数にすることで、挙動を近づける: 類似したデータレコードで訓練された類似のモデルは同様に振る舞う
	# ターゲットモデルとシャドーモデルのデータプールは重複無し → 最悪ケースを想定
	# シャドーモデル間のデータセットは重複許容
	target_train_size: int = 10520
	target_test_size: int = 10520
	shadow_train_size: int = 10520
	shadow_test_size: int = 10520
	# シード値
	seed: int = 42


