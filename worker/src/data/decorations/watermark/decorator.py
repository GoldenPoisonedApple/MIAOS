from __future__ import annotations

from PIL import Image

from src.data.decorations.watermark.transform import ImageWatermark


class WatermarkDecorator:
    """透かし合成デコレータ（PIL 変換のみ。対象選定は FractionalDecorator が担当）"""

    def __init__(self, watermark: ImageWatermark):
        self._watermark = watermark

	# 透かし合成
    def apply(
        self, image: Image.Image, *, global_idx: int, local_idx: int
    ) -> Image.Image:
        return self._watermark(image)
