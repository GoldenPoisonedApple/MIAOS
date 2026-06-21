import logging
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, ConcatDataset, Dataset
import src.core.config as cfg
from src.server_client.models import CreateExperimentRequest
import src.utils.minio_utils as minio_utils
from src.data.watermark import WatermarkConfig, FilterImage, ImageWatermark
import numpy as np
from sklearn.model_selection import train_test_split
import json
import os
from PIL import Image


logger = logging.getLogger(__name__)


# 動的にTransformを適応するSubset
class TransformedSubset(Dataset):
    """
    Transromを動的に適応したSubset
    画像変形などを適応するトレーニングデータと、それらを適応しないテストデータで混在を防ぐ
    Args:
        dataset: データセット
        indices: インデックス
        transform: 変換
        watermark_transform: 透かし合成（PIL in/out）
        watermarked_global_indices: 透かしを適用する full_dataset 上のグローバルインデックス集合
    """

    def __init__(
        self,
        dataset,
        indices,
        transform=None,
        watermark_transform=None,
        watermarked_global_indices=None,
    ):
        self.dataset = dataset
        self.indices = indices
        self.transform = transform
        self.watermark_transform = watermark_transform
        self.watermarked_global_indices = watermarked_global_indices or set()

    def __getitem__(self, idx):
        global_idx = self.indices[idx]
        x, y = self.dataset[global_idx]
        if (
            self.watermark_transform is not None
            and global_idx in self.watermarked_global_indices
        ):
            x = self.watermark_transform(x)
        if self.transform:
            x = self.transform(x)
        return x, y

    def __len__(self):
        return len(self.indices)


class dataset:
    DATASET_JSON_FILE_NAME = "dataset.json"

    def __init__(
        self,
        model_save_dir: str,
        settings: CreateExperimentRequest,
        assigned_model_path: str = None,
    ):
        self.settings = settings
        self.model_save_dir = model_save_dir
        self.assigned_model_path = assigned_model_path
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

        # 透かし設定の初期化
        self.watermark_config: WatermarkConfig | None = None
        self.watermark_transform: ImageWatermark | None = None
        self.watermarked_indices: dict[str, set[int]] = {}

        # モデルの読み込み
        if assigned_model_path is not None:
            with open(
                os.path.join(assigned_model_path, self.DATASET_JSON_FILE_NAME), "r"
            ) as f:
                specification = json.load(f)
            self.target_train_idx = np.array(specification["target_train_idx"])
            self.target_test_idx = np.array(specification["target_test_idx"])
            self.shadow_pool_indices = np.array(specification["shadow_pool_indices"])
            self._load_watermark_from_specification(specification)
        else:
            # データセットのインデックスを作成
            indices = np.arange(len(self.full_dataset))
            # データセットからターゲットモデルの学習用とテスト用のインデックスを分割
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
            self._initialize_watermark_for_new_experiment()
            # 保存
            specification = {
                "target_train_idx": self.target_train_idx.tolist(),
                "target_test_idx": self.target_test_idx.tolist(),
                "shadow_pool_indices": self.shadow_pool_indices.tolist(),
            }
            if self.watermark_config is not None:
                specification["watermark"] = {
                    "config": self.watermark_config.to_dict(),
                    "watermarked_indices": {
                        split: sorted(indices)
                        for split, indices in self.watermarked_indices.items()
                    },
                }
            with open(
                os.path.join(model_save_dir, self.DATASET_JSON_FILE_NAME), "w"
            ) as f:
                json.dump(specification, f)

        if self.watermark_transform is not None:
            self._save_watermark_preview()

    def _load_watermark_from_specification(self, specification: dict) -> None:
        watermark_spec = specification.get("watermark")
        if watermark_spec is None:
            return

        self.watermark_config = WatermarkConfig.from_dict(watermark_spec["config"])
        saved_indices = watermark_spec.get("watermarked_indices", {})
        self.watermarked_indices = {
            split: set(indices) for split, indices in saved_indices.items()
        }
        self._setup_watermark_transform()
        self._log_watermark_info()

    def _initialize_watermark_for_new_experiment(self) -> None:
        self.watermark_config = WatermarkConfig.from_hyperparameters(self.settings)
        if self.watermark_config is None:
            return

        split_pools = {
            "target_train": self.target_train_idx,
            "target_test": self.target_test_idx,
            "shadow_train": self.shadow_pool_indices,
            "shadow_test": self.shadow_pool_indices,
        }
        base_seed = self.settings.seed + self.watermark_config.seed_offset

        for split_offset, (split_name, fraction) in enumerate(
            self.watermark_config.active_splits()
        ):
            pool = split_pools[split_name]
            self.watermarked_indices[split_name] = self._select_watermarked_indices(
                pool,
                fraction,
                base_seed + split_offset,
            )

        self._setup_watermark_transform()
        self._log_watermark_info()

    def _setup_watermark_transform(self) -> None:
        if self.watermark_config is None:
            return

        filter_path = minio_utils.download_filter(self.watermark_config.filter_id)
        filter_image = FilterImage.load(filter_path)
        self.watermark_transform = ImageWatermark(filter_image=filter_image)

    def _select_watermarked_indices(
        self, pool_indices: np.ndarray, fraction: float, random_state: int
    ) -> set[int]:
        if fraction <= 0.0 or len(pool_indices) == 0:
            return set()
        if fraction >= 1.0:
            return set(int(idx) for idx in pool_indices)

        selected, _ = train_test_split(
            pool_indices,
            train_size=fraction,
            random_state=random_state,
        )
        return set(int(idx) for idx in selected)

    def _log_watermark_info(self) -> None:
        if self.watermark_config is None:
            return

        counts = {
            split: len(indices) for split, indices in self.watermarked_indices.items()
        }
        logger.info(
            "Watermark enabled: filter_id=%s, apply=%s, counts=%s",
            self.watermark_config.filter_id,
            self.watermark_config.apply,
            counts,
        )

    def _make_subset(
        self,
        indices: np.ndarray,
        split_name: str,
        transform,
    ) -> TransformedSubset:
        watermarked_global_indices = self.watermarked_indices.get(split_name, set())
        if (
            self.watermark_config is not None
            and self.watermark_config.fraction_for(split_name) <= 0.0
        ):
            watermarked_global_indices = set()

        return TransformedSubset(
            self.full_dataset,
            indices,
            transform=transform,
            watermark_transform=self.watermark_transform,
            watermarked_global_indices=watermarked_global_indices,
        )

    def _save_watermark_preview(self) -> None:
        """透かしあり/なしの代表サンプルを model_save_dir に保存する"""
        preview_path = os.path.join(self.model_save_dir, "watermark_preview.png")
        sample_idx = int(self.target_train_idx[0])
        original, _ = self.full_dataset[sample_idx]
        if not isinstance(original, Image.Image):
            return

        watermarked = self.watermark_transform(original)
        width, height = original.size
        combined = Image.new("RGB", (width * 2, height))
        combined.paste(original, (0, 0))
        combined.paste(watermarked, (width, 0))
        combined.save(preview_path)
        logger.info("Watermark preview saved: %s", preview_path)

    def get_target_dataloaders(self):
        target_train_dataset = self._make_subset(
            self.target_train_idx, "target_train", self.transform_train
        )
        target_test_dataset = self._make_subset(
            self.target_test_idx, "target_test", self.transform_test
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
            self.target_train_idx, "target_train", self.transform_test
        )
        target_test_dataset = self._make_subset(
            self.target_test_idx, "target_test", self.transform_test
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
            shadow_train_idx, "shadow_train", self.transform_train
        )
        shadow_test_dataset = self._make_subset(
            shadow_test_idx, "shadow_test", self.transform_test
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
            shadow_train_idx, "shadow_train", self.transform_test
        )
        shadow_test_dataset = self._make_subset(
            shadow_test_idx, "shadow_test", self.transform_test
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
