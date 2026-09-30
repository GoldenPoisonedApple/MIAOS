from __future__ import annotations

from collections.abc import Callable, Sequence

import torch
from PIL import Image

from src.data.decorations.watermark.decorator import WatermarkDecorator
from src.data.decorations.watermark.loader import WatermarkLoader


def build_decorated_plain_tensors(
    images: Sequence[Image.Image],
    loader: WatermarkLoader,
    filter_id: str,
    transform: Callable[[Image.Image], torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    透かし合成済み / 素の画像テンソルを返す（LF_Mult_MIA 系の攻撃用）。

    Normalize 前の PIL 段階で透かしを適用する（他の装飾と同じ段階）。
    """
    decorator = WatermarkDecorator(loader.get(filter_id))
    decorated_tensors: list[torch.Tensor] = []
    plain_tensors: list[torch.Tensor] = []
    for local_idx, image in enumerate(images):
        if image.mode != "RGB":
            image = image.convert("RGB")
        # Normalize 前の PIL 段階で透かしを適用（他の装飾と同じ段階）
        decorated_tensors.append(
            # 透かしを合成、transformを適応
            transform(decorator.apply(image, global_idx=local_idx, local_idx=local_idx))
        )
        plain_tensors.append(transform(image))
    
    # stack: リストをテンソルに変換
    return torch.stack(decorated_tensors), torch.stack(plain_tensors)
