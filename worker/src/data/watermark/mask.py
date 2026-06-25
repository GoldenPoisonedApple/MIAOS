from __future__ import annotations

import numpy as np
from PIL import Image

CIFAR_IMAGE_SIZE = 32


class FilterImage:
    """MinIO から取得した 32x32 RGBA フィルタ画像"""

    def __init__(self, rgb: np.ndarray, alpha: np.ndarray):
        if rgb.shape != (CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE, 3):
            raise ValueError(f"rgb must be ({CIFAR_IMAGE_SIZE}, {CIFAR_IMAGE_SIZE}, 3)")
        if alpha.shape != (CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE):
            raise ValueError(f"alpha must be ({CIFAR_IMAGE_SIZE}, {CIFAR_IMAGE_SIZE})")
        self._rgb = rgb.astype(np.float32)
        self._alpha = alpha.astype(np.float32)

    # PIL画像に変換
    def to_pil(self) -> Image.Image:
        rgb = np.clip(self._rgb, 0, 255).astype(np.uint8)
        return Image.fromarray(rgb, mode="RGB")

    @property
    def rgb(self) -> np.ndarray:
        return self._rgb

    @property
    def alpha(self) -> np.ndarray:
        return self._alpha

    @classmethod
    def load(cls, path: str) -> FilterImage:
        """フィルタ PNG を読み込み、32x32 RGBA に正規化する"""
        image = Image.open(path).convert("RGBA")
        if image.size != (CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE):
            image = image.resize(
                (CIFAR_IMAGE_SIZE, CIFAR_IMAGE_SIZE), Image.Resampling.LANCZOS
            )

        rgba = np.asarray(image, dtype=np.float32)
        rgb = rgba[:, :, :3]
        alpha = rgba[:, :, 3] / 255.0
        return cls(rgb=rgb, alpha=alpha)
