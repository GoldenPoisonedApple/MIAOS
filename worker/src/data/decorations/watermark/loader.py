from __future__ import annotations

from PIL import Image

import src.utils.minio_utils as minio_utils
from src.data.decorations.watermark.filter import FilterImage
from src.data.decorations.watermark.transform import ImageWatermark


class WatermarkLoader:
    """MinIO から透かしフィルタを取得する。FilterImage を filter_id 単位でキャッシュする。"""

    def __init__(self) -> None:
        # キー: フィルタID, 値: FilterImage
        # MINIOから取得 PNG読み込み
        # FilterImage: PNG画像など
        self._filter_cache: dict[str, FilterImage] = {}

    def _load_filter(self, filter_id: str) -> FilterImage:
        # キャッシュにない場合はフィルタを取得
        if filter_id not in self._filter_cache:
            # MINIOから取得 PNG読み込み
            filter_path = minio_utils.download_filter(filter_id)
            # FilterImage に変換
            self._filter_cache[filter_id] = FilterImage.load(filter_path)
        return self._filter_cache[filter_id]

    # 透かしフィルタをImageWatermarkに変換（CIFAR 画像へ alpha ブレンド合成する透かし変換）
    def get(self, filter_id: str) -> ImageWatermark:
        """CIFAR 画像へ alpha ブレンド合成する透かし変換を返す"""
        return ImageWatermark(filter_image=self._load_filter(filter_id))

    # フィルタ RGB のみを PIL で返す（合成前の素材確認用）
    def get_filter_pil(self, filter_id: str) -> Image.Image:
        """フィルタ RGB のみを PIL で返す（合成前の素材確認用）"""
        return self._load_filter(filter_id).to_pil()
