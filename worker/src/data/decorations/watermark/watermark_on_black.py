from __future__ import annotations

from PIL import Image

from src.data.decorations.watermark.filter import CIFAR_IMAGE_SIZE
from src.data.decorations.watermark.loader import WatermarkLoader


def build_watermark_on_black_pil(
    loader: WatermarkLoader,
    filter_id: str,
) -> Image.Image:
    """透かしフィルタを黒背景に alpha ブレンド合成した PIL 画像を返す。"""
    watermark = loader.get(filter_id)
    base = Image.new("RGB", (CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE), (0, 0, 0))
    return watermark(base)
