# インターフェース定義
from __future__ import annotations

from typing import Protocol

from PIL import Image


class SampleDecorator(Protocol):
    """Normalize 前の PIL 画像に対するサンプル単位の装飾"""

    def apply(
        self, image: Image.Image, *, global_idx: int, local_idx: int
    ) -> Image.Image: ...
