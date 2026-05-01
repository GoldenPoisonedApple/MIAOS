import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Subset, ConcatDataset
import config
import numpy as np
from sklearn.model_selection import train_test_split
import json
import os

class dataset:
	DATASET_JSON_FILE_NAME = "dataset.json"
    
	def __init__(self, model_save_dir, assigned_model_path=None):		
		# 画像変換処理 (Data Augmentation & Preprocessing)
		transform_train = transforms.Compose([
			transforms.ToTensor(), # PIL画像をTensor型(PyTorchの多次元配列)に変換し、[0.0, 1.0]にスケーリング
			transforms.Normalize((0.5071, 0.4865, 0.4409), (0.2673, 0.2564, 0.2762)) # CIFAR-100の平均と標準偏差で標準化 データセット固有の統計値
		])

		transform_test = transforms.Compose([
			transforms.ToTensor(),
			transforms.Normalize((0.5071, 0.4865, 0.4409), (0.2673, 0.2564, 0.2762))
		])

		# データセットのインスタンス化
		trainset = torchvision.datasets.CIFAR100(
      		root=config.DATA_DIR,
        	train=True, download=True, transform=transform_train
        )
		testset = torchvision.datasets.CIFAR100(
      		root=config.DATA_DIR,
        	train=False, download=True, transform=transform_test
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
			self.target_train_idx, remaining_idx = train_test_split(indices, train_size=config.TARGET_TRAIN_SIZE, random_state=config.SEED)
			self.target_test_idx, self.shadow_pool_indices = train_test_split(remaining_idx, train_size=config.TARGET_TEST_SIZE, random_state=config.SEED)
			# 保存
			with open(os.path.join(model_save_dir, self.DATASET_JSON_FILE_NAME), "w") as f:
				specification = {
					"target_train_idx": self.target_train_idx.tolist(),
					"target_test_idx": self.target_test_idx.tolist(),
					"shadow_pool_indices": self.shadow_pool_indices.tolist()
				}
				json.dump(specification, f)

	def get_target_dataloaders(self):
		# ターゲットモデルの学習用とテスト用のDataLoaderを作成
		# pin_memory=True: ページロックメモリを使用し、CPUからGPUへのデータ転送を高速化するオプション (推奨設定)
		# batch_size: 1回の学習に用いるデータ数, shuffle: データの順番をランダムにするか
		# num_workers: データローディングに使用するサブプロセスの数
		# shuffle=True: エポックごとにデータの順番をランダムに
		target_train_loader = DataLoader(
			Subset(self.full_dataset, self.target_train_idx), 
			batch_size=config.BATCH_SIZE, shuffle=True, 
			num_workers=config.NUM_WORKERS,
			pin_memory=True if config.DEVICE.type == 'cuda' else False
		)
		target_test_loader = DataLoader(
			Subset(self.full_dataset, self.target_test_idx), 
			batch_size=config.BATCH_SIZE, shuffle=False, 
			num_workers=config.NUM_WORKERS,
			pin_memory=True if config.DEVICE.type == 'cuda' else False
		)
		return target_train_loader, target_test_loader, len(self.target_train_idx), len(self.target_test_idx)

	def get_eval_target_dataloaders(self):
			"""評価およびロジット抽出用のシャッフル無効化データローダー"""
			target_train_loader = DataLoader(
				Subset(self.full_dataset, self.target_train_idx), 
				batch_size=config.BATCH_SIZE, shuffle=False,  # 順序を完全に固定
				num_workers=config.NUM_WORKERS,
				pin_memory=True if config.DEVICE.type == 'cuda' else False
			)
			target_test_loader = DataLoader(
				Subset(self.full_dataset, self.target_test_idx), 
				batch_size=config.BATCH_SIZE, shuffle=False,  # 順序を完全に固定
				num_workers=config.NUM_WORKERS,
				pin_memory=True if config.DEVICE.type == 'cuda' else False
			)
			return target_train_loader, target_test_loader, len(self.target_train_idx), len(self.target_test_idx)

	def get_shadow_dataloader(self, seed, shuffle=True):
		# 毎回新しくシャドーモデルの学習用とテスト用のインデックスを分割
		shadow_train_idx, remaining_idx = train_test_split(self.shadow_pool_indices, train_size=config.SHADOW_TRAIN_SIZE, random_state=config.SEED + seed)
		shadow_test_idx, _ = train_test_split(remaining_idx, train_size=config.SHADOW_TEST_SIZE, random_state=config.SEED + seed)
     
		# シャドーモデルの学習用とテスト用のDataLoaderを作成
		shadow_train_loader = DataLoader(
			Subset(self.full_dataset, shadow_train_idx), 
			batch_size=config.BATCH_SIZE, shuffle=shuffle, 
			num_workers=config.NUM_WORKERS,
			pin_memory=True if config.DEVICE.type == 'cuda' else False
		)
		shadow_test_loader = DataLoader(
			Subset(self.full_dataset, shadow_test_idx), 
			batch_size=config.BATCH_SIZE, shuffle=False, 
			num_workers=config.NUM_WORKERS,
			pin_memory=True if config.DEVICE.type == 'cuda' else False
		)
		return shadow_train_loader, shadow_test_loader, len(shadow_train_idx), len(shadow_test_idx)