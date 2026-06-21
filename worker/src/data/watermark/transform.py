from __future__ import annotations

import numpy as np
from PIL import Image

from src.data.watermark.mask import WatermarkMask


class ShapeWatermark:
    """PIL 画像に形状マスクベースの透かしを合成する"""

    def __init__(
        self,
        mask: WatermarkMask,
        color: tuple[int, int, int],
        opacity: float,
    ):
        self._alpha_map = mask.alpha_map
        self._color = np.array(color, dtype=np.float32)
        self._opacity = opacity

    def __call__(self, image: Image.Image) -> Image.Image:
        if image.mode != "RGB":
            image = image.convert("RGB")

        img_array = np.asarray(image, dtype=np.float32)
        blend_weight = self._alpha_map[:, :, np.newaxis] * self._opacity
        color = self._color.reshape(1, 1, 3)

        result = img_array * (1.0 - blend_weight) + color * blend_weight
        result = np.clip(result, 0, 255).astype(np.uint8)
        return Image.fromarray(result, mode="RGB")
