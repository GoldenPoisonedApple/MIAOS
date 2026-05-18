import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, ConcatDataset, Dataset
import src.core.config as cfg
from src.server_client.models import CreateExperimentRequest
import numpy as np
from sklearn.model_selection import train_test_split
import json
import os

# 動的にTransformを適応するSubset
class TransformedSubset(Dataset):
    """
    Transromを動的に適応したSubset
    画像変形などを適応するトレーニングデータと、それらを適応しないテストデータで混在を防ぐ
    Args:
        dataset: データセット
        indices: インデックス
        transform: 変換
    """

    def __init__(self, dataset, indices, transform=None):
        self.dataset = dataset
        self.indices = indices
        self.transform = transform
    def __getitem__(self, idx):
        x, y = self.dataset[self.indices[idx]]
        if self.transform:
            x = self.transform(x)
        return x, y
    def __len__(self):
        return len(self.indices)

class dataset:
	DATASET_JSON_FILE_NAME = "dataset.json"
    
	def __init__(self, model_save_dir: str, settings: CreateExperimentRequest, assigned_model_path: str = None):
		self.settings = settings
		# 画像変換処理 (Data Augmentation & Preprocessing)記述
		self.transform_train = transforms.Compose([
			# 将来的には変換処理も存在
			transforms.ToTensor(), # PIL画像をTensor型(PyTorchの多次元配列)に変換し、[0.0, 1.0]にスケーリング
			transforms.Normalize((0.5071, 0.4865, 0.4409), (0.2673, 0.2564, 0.2762)) # CIFAR-100の平均と標準偏差で標準化 データセット固有の統計値
		])

		self.transform_test = transforms.Compose([
			transforms.ToTensor(),
			transforms.Normalize((0.5071, 0.4865, 0.4409), (0.2673, 0.2564, 0.2762))
		])

		# データセットのインスタンス化
		# 生のPIL画像のまま読み込み
		trainset = torchvision.datasets.CIFAR100(
      		root=cfg.DATA_DIR,
        	train=True, download=True, transform=None
        )
		testset = torchvision.datasets.CIFAR100(
      		root=cfg.DATA_DIR,
        	train=False, download=True, transform=None
        )
		self.full_dataset = ConcatDataset([trainset, testset])

		# モデルの読み込み
		if assigned_model_path is not None:
			with open(os.path.join(assigned_model_path, self.DATASET_JSON_FILE_NAME), "r") as f:
				specification = json.load(f)
			self.target_train_idx = np.array(specification["target_train_idx"])
			self.target_test_idx = np.array(specification["target_test_idx"])
			self.shadow_pool_indices = np.array(specification["shadow_pool_indices"])
		else:
			# データセットのインデックスを作成
			indices = np.arange(len(self.full_dataset))
			# データセットからターゲットモデルの学習用とテスト用のインデックスを分割
			self.target_train_idx, remaining_idx = train_test_split(indices, train_size=settings.target_train_size, random_state=settings.seed)
			self.target_test_idx, self.shadow_pool_indices = train_test_split(remaining_idx, train_size=settings.target_test_size, random_state=settings.seed)
			# 保存
			with open(os.path.join(model_save_dir, self.DATASET_JSON_FILE_NAME), "w") as f:
				specification = {
					"target_train_idx": self.target_train_idx.tolist(),
					"target_test_idx": self.target_test_idx.tolist(),
					"shadow_pool_indices": self.shadow_pool_indices.tolist()
				}
				json.dump(specification, f)

	def get_target_dataloaders(self):
		target_train_dataset = TransformedSubset(self.full_dataset, self.target_train_idx, self.transform_train)
		target_test_dataset = TransformedSubset(self.full_dataset, self.target_test_idx, self.transform_test)
     
		# ターゲットモデルの学習用とテスト用のDataLoaderを作成
		# pin_memory=True: ページロックメモリを使用し、CPUからGPUへのデータ転送を高速化するオプション (推奨設定)
		# batch_size: 1回の学習に用いるデータ数, shuffle: データの順番をランダムにするか
		# num_workers: データローディングに使用するサブプロセスの数
		# shuffle=True: エポックごとにデータの順番をランダムに
		target_train_loader = DataLoader(
			target_train_dataset, 
			batch_size=self.settings.batch_size, shuffle=True, 
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		target_test_loader = DataLoader(
			target_test_dataset, 
			batch_size=self.settings.batch_size, shuffle=False, 
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		return target_train_loader, target_test_loader, len(self.target_train_idx), len(self.target_test_idx)

	def get_eval_target_dataloaders(self):
		"""評価およびロジット抽出用のシャッフル無効化データローダー"""
		# 修正箇所: 評価・特徴量抽出時は、学習データであっても transform_testを使う
		# 精度を正確に測定するためデータに対するランダムな摂動が許容されないため、テストデータと同じ変換処理を適用
		target_train_dataset = TransformedSubset(self.full_dataset, self.target_train_idx, transform=self.transform_test)
		target_test_dataset = TransformedSubset(self.full_dataset, self.target_test_idx, transform=self.transform_test)
     
		target_train_loader = DataLoader(
			target_train_dataset, 
			batch_size=self.settings.batch_size, shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		target_test_loader = DataLoader(
			target_test_dataset, 
			batch_size=self.settings.batch_size, shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		return target_train_loader, target_test_loader, len(self.target_train_idx), len(self.target_test_idx)

	def get_shadow_dataloader(self, seed):
		# 毎回新しくシャドーモデルの学習用とテスト用のインデックスを分割
		shadow_train_idx, remaining_idx = train_test_split(self.shadow_pool_indices, train_size=self.settings.shadow_train_size, random_state=self.settings.seed + seed)
		shadow_test_idx, _ = train_test_split(remaining_idx, train_size=self.settings.shadow_test_size, random_state=self.settings.seed + seed)
		# 動的にTransformを適応したSubsetを作成
		shadow_train_dataset = TransformedSubset(self.full_dataset, shadow_train_idx, transform=self.transform_train)
		shadow_test_dataset = TransformedSubset(self.full_dataset, shadow_test_idx, transform=self.transform_test)
     
		# シャドーモデルの学習用とテスト用のDataLoaderを作成
		shadow_train_loader = DataLoader(
			shadow_train_dataset, 
			batch_size=self.settings.batch_size, shuffle=True, 
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		shadow_test_loader = DataLoader(
			shadow_test_dataset, 
			batch_size=self.settings.batch_size, shuffle=False, 
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		return shadow_train_loader, shadow_test_loader, len(shadow_train_idx), len(shadow_test_idx)

	def get_eval_shadow_dataloader(self, seed):
		"""評価およびロジット抽出用のシャッフル無効化データローダー"""
		# 毎回新しくシャドーモデルの学習用とテスト用のインデックスを分割
		shadow_train_idx, remaining_idx = train_test_split(self.shadow_pool_indices, train_size=self.settings.shadow_train_size, random_state=self.settings.seed + seed)
		shadow_test_idx, _ = train_test_split(remaining_idx, train_size=self.settings.shadow_test_size, random_state=self.settings.seed + seed)
		# 精度を正確に測定するためデータに対するランダムな摂動が許容されないため、テストデータと同じ変換処理を適用
		shadow_train_dataset = TransformedSubset(self.full_dataset, shadow_train_idx, transform=self.transform_test)
		shadow_test_dataset = TransformedSubset(self.full_dataset, shadow_test_idx, transform=self.transform_test)

		shadow_train_loader = DataLoader(
			shadow_train_dataset, 
			batch_size=self.settings.batch_size, shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		shadow_test_loader = DataLoader(
			shadow_test_dataset, 
			batch_size=self.settings.batch_size, shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=True if cfg.DEVICE.type == 'cuda' else False
		)
		return shadow_train_loader, shadow_test_loader, len(shadow_train_idx), len(shadow_test_idx)