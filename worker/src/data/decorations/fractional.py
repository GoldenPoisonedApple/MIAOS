from __future__ import annotations

from PIL import Image

from src.data.decorations.protocol import SampleDecorator


class FractionalDecorator:
    """fraction に基づき選定されたインデックスにのみ inner 装飾を適用する"""

    def __init__(self, inner: SampleDecorator, indices: set[int]):
        self._inner = inner
        self._indices = indices

    def apply(
        self, image: Image.Image, *, global_idx: int, local_idx: int
    ) -> Image.Image:
        if global_idx not in self._indices:
            return image
        return self._inner.apply(image, global_idx=global_idx, local_idx=local_idx)
