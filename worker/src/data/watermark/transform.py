from __future__ import annotations

import numpy as np
from PIL import Image

from src.data.watermark.mask import FilterImage


class ImageWatermark:
    """PIL 画像にフィルタ画像を alpha ブレンドで合成する"""

    def __init__(self, filter_image: FilterImage):
        self._rgb = filter_image.rgb
        self._alpha = filter_image.alpha

    def __call__(self, image: Image.Image) -> Image.Image:
        if image.mode != "RGB":
            image = image.convert("RGB")

        img_array = np.asarray(image, dtype=np.float32)
        blend_weight = self._alpha[:, :, np.newaxis]

        result = img_array * (1.0 - blend_weight) + self._rgb * blend_weight
        result = np.clip(result, 0, 255).astype(np.uint8)
        return Image.fromarray(result, mode="RGB")
