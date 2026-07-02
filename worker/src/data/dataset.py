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
from src.data.decorations.watermark.loader import WatermarkLoader
from src.data.decorations.watermark.probe import save_comparison_preview as save_watermark_preview
from src.data.decorations.display_mask.preview import save_comparison_preview as save_display_mask_preview
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

        # 装飾設定の読み込み
        self._decoration_builder = SampleDecoratorBuilder(
            experiment_seed=int(self.settings.seed),
        )

        # 装飾プレビューを保存
        if self.decoration_config.has_watermark():
            self._save_watermark_preview()
        if self.decoration_config.has_display_mask():
            self._save_display_mask_preview()

    def get_watermark_loader(self) -> WatermarkLoader:
        """透かし装飾用 loader（builder 経由で lazy 初期化）"""
        return self._decoration_builder.get_watermark_loader()

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

    def _save_watermark_preview(self) -> None:
        """透かしあり/なしの代表サンプルを role ごとに model_save_dir に保存する"""
        roles = self.decoration_config.watermark_roles()
        if not roles:
            return

        sample_idx = int(self.target_train_idx[0])
        original, _ = self.full_dataset[sample_idx]
        if not isinstance(original, Image.Image):
            return

        loader = self._decoration_builder.get_watermark_loader()
        for role, filter_id in roles:
            preview_path = os.path.join(
                self.model_save_dir, f"watermark_preview_{role}.png"
            )
            save_watermark_preview(loader, filter_id, original, preview_path)

    def _save_display_mask_preview(self) -> None:
        """表示マスク適用前後の代表サンプルを role ごとに model_save_dir に保存する"""
        roles = self.decoration_config.display_mask_roles()
        if not roles:
            return

        sample_idx = int(self.target_train_idx[0])
        original, _ = self.full_dataset[sample_idx]
        if not isinstance(original, Image.Image):
            return

        for role, spec in roles:
            preview_path = os.path.join(
                self.model_save_dir, f"display_mask_preview_{role}.png"
            )
            save_display_mask_preview(spec, original, preview_path)

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
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        target_test_loader = DataLoader(
            target_test_dataset,
            batch_size=self.settings.batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
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
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        target_test_loader = DataLoader(
            target_test_dataset,
            batch_size=self.settings.batch_size,
            shuffle=False,  # 順序を完全に固定
            num_workers=0,
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        return (
            target_train_loader,
            target_test_loader,
            len(self.target_train_idx),
            len(self.target_test_idx),
        )

    def get_shadow_dataloader(self, seed):
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
        )
        shadow_test_dataset = self._make_subset(
            shadow_test_idx,
            self.transform_test,
        )

        # シャドーモデルの学習用とテスト用のDataLoaderを作成
        shadow_train_loader = DataLoader(
            shadow_train_dataset,
            batch_size=self.settings.batch_size,
            shuffle=True,
            num_workers=0,
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        shadow_test_loader = DataLoader(
            shadow_test_dataset,
            batch_size=self.settings.batch_size,
            shuffle=False,
            num_workers=0,
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        return (
            shadow_train_loader,
            shadow_test_loader,
            len(shadow_train_idx),
            len(shadow_test_idx),
        )

    def get_eval_shadow_dataloader(self, seed):
        """評価およびロジット抽出用のシャッフル無効化データローダー"""
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
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        shadow_test_loader = DataLoader(
            shadow_test_dataset,
            batch_size=self.settings.batch_size,
            shuffle=False,  # 順序を完全に固定
            num_workers=0,
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        return (
            shadow_train_loader,
            shadow_test_loader,
            len(shadow_train_idx),
            len(shadow_test_idx),
        )

    def get_cifar_probe_dataloader(self, global_idx: int | None = None):
        """対照用: 透かしなし CIFAR 1枚の probe DataLoader"""
        if global_idx is None:
            global_idx = int(self.target_train_idx[0])

        x, y = self.full_dataset[global_idx]
        if not isinstance(x, Image.Image):
            raise TypeError("Expected PIL image from full_dataset")

        tensor = self.transform_test(x).unsqueeze(0)
        label = torch.tensor([int(y)], dtype=torch.long)
        loader = DataLoader(
            TensorDataset(tensor, label),
            batch_size=1,
            shuffle=False,
            num_workers=0,
            pin_memory=True if cfg.DEVICE.type == "cuda" else False,
        )
        return loader, global_idx, int(y)
