import logging
import os

import numpy as np
import torch
import torchvision
import torchvision.transforms as transforms
from PIL import Image
from sklearn.model_selection import train_test_split
from torch.utils.data import ConcatDataset, DataLoader, TensorDataset

import src.core.config as cfg
from src.data.decorations import (
	DecorationConfig,
	DecorationSpec,
	SampleDecoratorBuilder,
	TransformedSubset,
)
from src.data.decorations.preview import save_decoration_preview
from src.data.decorations.watermark.loader import WatermarkLoader
from src.data.decorations.watermark.watermark_on_black import build_watermark_on_black_pil
from src.data.decorations.config import WatermarkDecorationSpec
from src.server_client.models import CreateExperimentRequest

logger = logging.getLogger(__name__)


class dataset:
	def __init__(
		self,
		model_save_dir: str,
		settings: CreateExperimentRequest,
	):
		self.settings = settings
		self.model_save_dir = model_save_dir
		# 画像変換処理 (Data Augmentation & Preprocessing)記述
		self.transform_train = transforms.Compose(
			[
				# 将来的には変換処理も存在
				transforms.ToTensor(),  # PIL画像をTensor型(PyTorchの多次元配列)に変換し、[0.0, 1.0]にスケーリング
				transforms.Normalize(
					(0.5071, 0.4865, 0.4409), (0.2673, 0.2564, 0.2762)
				),  # CIFAR-100の平均と標準偏差で標準化 データセット固有の統計値
			]
		)

		self.transform_test = transforms.Compose(
			[
				transforms.ToTensor(),
				transforms.Normalize(
					(0.5071, 0.4865, 0.4409), (0.2673, 0.2564, 0.2762)
				),
			]
		)

		# データセットのインスタンス化
		# 生のPIL画像のまま読み込み
		trainset = torchvision.datasets.CIFAR100(
			root=cfg.DATA_DIR, train=True, download=True, transform=None
		)
		testset = torchvision.datasets.CIFAR100(
			root=cfg.DATA_DIR, train=False, download=True, transform=None
		)
		self.full_dataset = ConcatDataset([trainset, testset])

		# 装飾設定の読み込み
		self.decoration_config = DecorationConfig.from_request(settings)
		# 装飾設定の読み込み
		self._decoration_builder = SampleDecoratorBuilder(
			experiment_seed=int(self.settings.seed),
		)

		# データセットのインデックスを作成（常に request の seed / sizes から計算）
		indices = np.arange(len(self.full_dataset))
		self.target_train_idx, remaining_idx = train_test_split(
			indices,
			train_size=settings.target_train_size,
			random_state=settings.seed,
		)
		self.target_test_idx, self.shadow_pool_indices = train_test_split(
			remaining_idx,
			train_size=settings.target_test_size,
			random_state=settings.seed,
		)

		# 装飾プレビューを保存
		self._save_decoration_preview()

	def get_watermark_loader(self) -> WatermarkLoader:
		"""透かし装飾用 loader（builder 経由で lazy 初期化）"""
		return self._decoration_builder.get_watermark_loader()
	
	# 攻撃用透かし画像のデータローダー取得
	def get_attack_watermark_dataloader(self) -> DataLoader:
		"""attack_decoration の透かし1枚を DataLoader として返す（get_predictions 用）。"""
		attack_spec = self.decoration_config.attack_decoration
		if not isinstance(attack_spec, WatermarkDecorationSpec):
			raise ValueError(
				f"attack_decoration must be watermark, got: {attack_spec!r}"
			)

		watermark_pil = build_watermark_on_black_pil(
			self.get_watermark_loader(),
			attack_spec.filter_id,
		)
		# (3, H, W) → (1, 3, H, W): TensorDataset のサンプル数を 1 にする
		tensor = self.transform_test(watermark_pil).unsqueeze(0)
		dummy_label = torch.tensor([0], dtype=torch.long)  # 正解ラベルを持たないためダミー
		return DataLoader(
			TensorDataset(tensor, dummy_label),
			batch_size=1,
			shuffle=False,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)

	# データセット作成(装飾適用)
	def _make_subset(
		self,
		indices: np.ndarray,
		transform,
		decoration_spec: DecorationSpec | None = None,
	) -> TransformedSubset:
		# 装飾設定から装飾を確定
		sample_decorator = self._decoration_builder.build(
			spec=decoration_spec,
			pool_indices=indices,
		)

		return TransformedSubset(
			self.full_dataset,
			indices,
			transform=transform,
			sample_decorator=sample_decorator,
		)

	def _save_decoration_preview(self) -> None:
		"""plain / target / eval / shadow / attack の5列プレビューを model_save_dir に保存する"""
		sample_idx = int(self.target_train_idx[0])
		original, _ = self.full_dataset[sample_idx]
		if not isinstance(original, Image.Image):
			return

		preview_path = os.path.join(self.model_save_dir, "decoration_preview.png")
		save_decoration_preview(
			self._decoration_builder,
			self.decoration_config,
			original,
			preview_path,
		)

	# ターゲットモデル用データローダーを取得
	def get_target_dataloaders(self):
		"""ターゲットモデル用データローダーを取得"""
		target_train_dataset = self._make_subset(
			self.target_train_idx,
			self.transform_train,
			decoration_spec=self.decoration_config.target_train_decoration,
		)
		target_test_dataset = self._make_subset(
			self.target_test_idx,
			self.transform_test,
		)

		# ターゲットモデルの学習用とテスト用のDataLoaderを作成
		# pin_memory=True: ページロックメモリを使用し、CPUからGPUへのデータ転送を高速化するオプション (推奨設定)
		# batch_size: 1回の学習に用いるデータ数, shuffle: データの順番をランダムにするか
		# num_workers: データローディングに使用するサブプロセスの数
		# shuffle=True: エポックごとにデータの順番をランダムに
		target_train_loader = DataLoader(
			target_train_dataset,
			batch_size=self.settings.batch_size,
			shuffle=True,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		target_test_loader = DataLoader(
			target_test_dataset,
			batch_size=self.settings.batch_size,
			shuffle=False,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		return (
			target_train_loader,
			target_test_loader,
			len(self.target_train_idx),
			len(self.target_test_idx),
		)

	def get_eval_target_dataloaders(self):
		"""評価およびロジット抽出用のシャッフル無効化データローダー"""
		# 修正箇所: 評価・特徴量抽出時は、学習データであっても transform_testを使う
		# 精度を正確に測定するためデータに対するランダムな摂動が許容されないため、テストデータと同じ変換処理を適用
		target_train_dataset = self._make_subset(
			self.target_train_idx,
			self.transform_test,
			decoration_spec=self.decoration_config.eval_decoration,
		)
		target_test_dataset = self._make_subset(
			self.target_test_idx,
			self.transform_test,
			decoration_spec=self.decoration_config.eval_decoration,
		)

		target_train_loader = DataLoader(
			target_train_dataset,
			batch_size=self.settings.batch_size,
			shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		target_test_loader = DataLoader(
			target_test_dataset,
			batch_size=self.settings.batch_size,
			shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		return (
			target_train_loader,
			target_test_loader,
			len(self.target_train_idx),
			len(self.target_test_idx),
		)

	def get_eval_decorated_sample(self, sample_idx: int) -> tuple[Image.Image, int]:
		"""攻撃クエリ順（train→test）の sample_idx について、eval_decoration 適用後の PIL 画像を返す。"""
		train_size = len(self.target_train_idx)
		if sample_idx < train_size:
			indices = self.target_train_idx
			local_idx = sample_idx
		else:
			indices = self.target_test_idx
			local_idx = sample_idx - train_size

		eval_subset = self._make_subset(
			indices,
			transform=None,
			decoration_spec=self.decoration_config.eval_decoration,
		)
		image, label = eval_subset[local_idx]
		return image, int(label)

	def get_attack_query_indices(self) -> np.ndarray:
		"""Online LiRA の攻撃対象サンプル（target train + test）のグローバルインデックス"""
		return np.concatenate([self.target_train_idx, self.target_test_idx])

	def build_online_lira_keep_matrix(self, num_shadows: int, seed: int) -> np.ndarray:
		"""
		Online LiRA 用 keep 行列を生成する。
		各クエリサンプルがちょうど半数のシャドーモデルで IN になるよう割り当てる。
		Returns:
				shape (num_shadows, num_query_samples) の bool 配列
		"""
		# 対象データ取得
		query_indices = self.get_attack_query_indices()
		num_query = len(query_indices)
		# 一様分布からランダムな数値を生成
		rng = np.random.RandomState(seed)	# 乱数生成器の作成
		# [0, 1) で (行: num_shadows, 列: num_query) の形状の行列作成
		uniforms = rng.uniform(0, 1, size=(num_shadows, num_query))
		# 列方向(num_query)にソート: shadowの順位を決定
		order = uniforms.argsort(axis=0)
		# shadowの半数
		num_in = num_shadows // 2
		# 要素 < num_in の条件を満たす要素を True にし、それ以外を False にする: 丁度半数のshadowがINになる
		return order < num_in

	def get_online_lira_shadow_dataloader(
		self,
		seed: int,
		query_indices: np.ndarray,
		query_keep: np.ndarray,
	):
		"""
		Online LiRA 用シャドーデータローダー。
		shadow_pool からの分割に加え、query_keep が True のクエリサンプルを学習集合へ含める。
		"""
		# シャドーモデル用のデータセットから学習用とテスト用のインデックスを分割
		shadow_train_idx, remaining_idx = train_test_split(
			self.shadow_pool_indices,
			train_size=self.settings.shadow_train_size,
			random_state=self.settings.seed + seed,
		)
		shadow_test_idx, _ = train_test_split(
			remaining_idx,
			train_size=self.settings.shadow_test_size,
			random_state=self.settings.seed + seed,
		)
		# 対象データのうち IN と判定されたものを学習集合に追加
		query_in_idx = query_indices[query_keep]	# 対象データのうち IN と判定されたもののインデックス
		# 結合
		if len(query_in_idx) > 0:
			shadow_train_idx = np.concatenate([shadow_train_idx, query_in_idx])
			shadow_train_idx = np.unique(shadow_train_idx)	# 重複を削除: 重複は存在しないが念のため

		shadow_train_dataset = self._make_subset(
			shadow_train_idx,
			self.transform_train,
		)
		shadow_test_dataset = self._make_subset(
			shadow_test_idx,
			self.transform_test,
		)

		shadow_train_loader = DataLoader(
			shadow_train_dataset,
			batch_size=self.settings.batch_size,
			shuffle=True,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		shadow_test_loader = DataLoader(
			shadow_test_dataset,
			batch_size=self.settings.batch_size,
			shuffle=False,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		return (
			shadow_train_loader,
			shadow_test_loader,
			len(shadow_train_idx),
			len(shadow_test_idx),
		)

	def get_shadow_dataloader(self, seed, is_decoration: bool = False):
		# 毎回新しくシャドーモデルの学習用とテスト用のインデックスを分割
		shadow_train_idx, remaining_idx = train_test_split(
			self.shadow_pool_indices,
			train_size=self.settings.shadow_train_size,
			random_state=self.settings.seed + seed,
		)
		shadow_test_idx, _ = train_test_split(
			remaining_idx,
			train_size=self.settings.shadow_test_size,
			random_state=self.settings.seed + seed,
		)
		# 動的にTransformを適応したSubsetを作成
		shadow_train_dataset = self._make_subset(
			shadow_train_idx,
			self.transform_train,
			decoration_spec=self.decoration_config.shadow_decoration if is_decoration else None,
		)
		shadow_test_dataset = self._make_subset(
			shadow_test_idx,
			self.transform_test,
			decoration_spec=self.decoration_config.shadow_decoration if is_decoration else None,
		)

		# シャドーモデルの学習用とテスト用のDataLoaderを作成
		shadow_train_loader = DataLoader(
			shadow_train_dataset,
			batch_size=self.settings.batch_size,
			shuffle=True,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		shadow_test_loader = DataLoader(
			shadow_test_dataset,
			batch_size=self.settings.batch_size,
			shuffle=False,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		return (
			shadow_train_loader,
			shadow_test_loader,
			len(shadow_train_idx),
			len(shadow_test_idx),
		)

	def get_eval_shadow_dataloader(self, seed):
		"""Shokri 評価用のシャッフル無効化データローダー"""
		# 毎回新しくシャドーモデルの学習用とテスト用のインデックスを分割
		shadow_train_idx, remaining_idx = train_test_split(
			self.shadow_pool_indices,
			train_size=self.settings.shadow_train_size,
			random_state=self.settings.seed + seed,
		)
		shadow_test_idx, _ = train_test_split(
			remaining_idx,
			train_size=self.settings.shadow_test_size,
			random_state=self.settings.seed + seed,
		)
		# 精度を正確に測定するためデータに対するランダムな摂動が許容されないため、テストデータと同じ変換処理を適用
		shadow_train_dataset = self._make_subset(
			shadow_train_idx,
			self.transform_test,
			decoration_spec=self.decoration_config.eval_decoration,
		)
		shadow_test_dataset = self._make_subset(
			shadow_test_idx,
			self.transform_test,
			decoration_spec=self.decoration_config.eval_decoration,
		)

		shadow_train_loader = DataLoader(
			shadow_train_dataset,
			batch_size=self.settings.batch_size,
			shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		shadow_test_loader = DataLoader(
			shadow_test_dataset,
			batch_size=self.settings.batch_size,
			shuffle=False,  # 順序を完全に固定
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)
		return (
			shadow_train_loader,
			shadow_test_loader,
			len(shadow_train_idx),
			len(shadow_test_idx),
		)
