from __future__ import annotations

import logging
import os

from PIL import Image

from src.data.decorations.display_mask.decorator import DisplayMaskDecorator
from src.data.decorations.config import DisplayMaskDecorationSpec

logger = logging.getLogger(__name__)


def save_comparison_preview(
    spec: DisplayMaskDecorationSpec,
    original: Image.Image,
    output_path: str,
) -> None:
    """マスク適用前後の比較画像を保存する"""
    decorator = DisplayMaskDecorator(
        width=spec.width,
        height=spec.height,
        x=spec.x,
        y=spec.y,
    )
    masked = decorator.apply(original, global_idx=0, local_idx=0)
    width, height = original.size
    combined = Image.new("RGB", (width * 2, height))
    combined.paste(original, (0, 0))
    combined.paste(masked, (width, 0))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    combined.save(output_path)
    logger.info("Display mask preview saved: %s", output_path)
