from __future__ import annotations

import numpy as np
from PIL import Image

CIFAR_IMAGE_SIZE = 32


class WatermarkMask:
    """透かし用マスク PNG を読み込み、CIFAR-100 キャンバス上の alpha マップを生成する"""

    def __init__(self, alpha_map: np.ndarray):
        if alpha_map.shape != (CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE):
            raise ValueError(
                f"alpha_map must be ({CIFAR_IMAGE_SIZE}, {CIFAR_IMAGE_SIZE})"
            )
        self._alpha_map = alpha_map.astype(np.float32)

    @property
    def alpha_map(self) -> np.ndarray:
        return self._alpha_map

    @classmethod
    def load(cls, path: str, position: tuple[int, int] = (0, 0)) -> WatermarkMask:
        """マスク PNG を読み込み、32x32 キャンバス上に配置した alpha マップを返す"""
        image = Image.open(path)
        mask_array = cls._extract_alpha(image)

        mask_h, mask_w = mask_array.shape
        if mask_w > CIFAR_IMAGE_SIZE or mask_h > CIFAR_IMAGE_SIZE:
            mask_image = Image.fromarray((mask_array * 255).astype(np.uint8), mode="L")
            mask_image = mask_image.resize(
                (CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE), Image.Resampling.LANCZOS
            )
            mask_array = np.asarray(mask_image, dtype=np.float32) / 255.0

        alpha_map = np.zeros((CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE), dtype=np.float32)
        x_offset, y_offset = position
        mask_h, mask_w = mask_array.shape

        y_start = max(0, y_offset)
        x_start = max(0, x_offset)
        y_end = min(CIFAR_IMAGE_SIZE, y_offset + mask_h)
        x_end = min(CIFAR_IMAGE_SIZE, x_offset + mask_w)

        src_y_start = y_start - y_offset
        src_x_start = x_start - x_offset
        src_y_end = src_y_start + (y_end - y_start)
        src_x_end = src_x_start + (x_end - x_start)

        if y_end > y_start and x_end > x_start:
            alpha_map[y_start:y_end, x_start:x_end] = mask_array[
                src_y_start:src_y_end, src_x_start:src_x_end
            ]

        return cls(alpha_map)

    @staticmethod
    def _extract_alpha(image: Image.Image) -> np.ndarray:
        """白=透かし領域、黒=非透かし。alpha チャンネルがあれば優先"""
        if image.mode in ("RGBA", "LA"):
            alpha = np.asarray(image.split()[-1], dtype=np.float32) / 255.0
            return alpha

        grayscale = image.convert("L")
        luminance = np.asarray(grayscale, dtype=np.float32) / 255.0
        return luminance
