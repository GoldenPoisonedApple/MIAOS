import os
import torch

# シャドーモデルの数
NUM_SHADOW_MODELS = 20
# クラス数
NUM_CLASSES = 100

# バッチサイズ: 1回の重み更新に用いるサンプルの数
BATCH_SIZE = 256
# 最大エポック数: データセット全体を学習する回数
MAX_EPOCHS = 60
# データロードに使用するサブプロセス数
# CIFARのやつはオンメモリより0で
NUM_WORKERS = os.cpu_count() or 4
# NUM_WORKERS = 0

# デバイスの設定 (GPUが利用可能であればCUDA、そうでなければCPU)
# CUDA: Compute Unified Device Architecture (NVIDIAの並列計算プラットフォーム)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# データセットの保存先ディレクトリ
DATA_DIR = './data'

# モデルデータの保存先ディレクトリ
MODEL_DIR = './models'

# 指定ターゲットモデル
ASSIGNED_MODEL_PATH = ""

# モデル保存名
TARGET_MODEL_NAME = "target_model.pth"
ATTACK_DATASET_NAME = "attack_dataset.pth"
ATTACK_MODEL_NAME_TEMPLATE = "attack_models/{}.pth"

# データセットの数
# 各モデルの訓練データとテストデータは重複無し、同サイズ
# → メンバと非メンバを同数にすることでBaseを50%にする
# → ターゲットとシャドーでの数を同数にすることで、挙動を近づける: 類似したデータレコードで訓練された類似のモデルは同様に振る舞う
# ターゲットモデルとシャドーモデルのデータプールは重複無し → 最悪ケースを想定
# シャドーモデル間のデータセットは重複許容
TARGET_TRAIN_SIZE = 10520
TARGET_TEST_SIZE = 10520
SHADOW_TRAIN_SIZE = 10520
SHADOW_TEST_SIZE = 10520

# シード値の設定 (再現性の確保のため)
SEED = 42
torch.manual_seed(SEED)
if torch.cuda.is_available():
	torch.cuda.manual_seed_all(SEED)
 
 
