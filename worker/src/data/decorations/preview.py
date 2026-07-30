from __future__ import annotations

import logging
import os

from PIL import Image

from src.data.decorations.builder import SampleDecoratorBuilder
from src.data.decorations.config import (
    DecorationConfig,
    DecorationSpec,
    DisplayMaskDecorationSpec,
    WatermarkDecorationSpec,
)
from src.data.decorations.display_mask.decorator import DisplayMaskDecorator
from src.data.decorations.watermark.decorator import WatermarkDecorator

logger = logging.getLogger(__name__)


def apply_decoration_preview(
    builder: SampleDecoratorBuilder,
    spec: DecorationSpec | None,
    image: Image.Image,
) -> Image.Image:
    """プレビュー用: fraction を無視し、1枚に装飾を必ず適用する。"""
    if spec is None:
        return image

    if isinstance(spec, WatermarkDecorationSpec):
        decorator = WatermarkDecorator(
            builder.get_watermark_loader().get(spec.filter_id)
        )
    elif isinstance(spec, DisplayMaskDecorationSpec):
        # 表示領域マスクオブジェクト作成
        decorator = DisplayMaskDecorator(
            width=spec.width,
            height=spec.height,
            x=spec.x,
            y=spec.y,
        )
    else:
        raise ValueError(f"Unknown decoration spec: {spec!r}")

    return decorator.apply(image, global_idx=0, local_idx=0)


def save_decoration_preview(
    builder: SampleDecoratorBuilder,
    config: DecorationConfig,
    original: Image.Image,
    output_path: str,
) -> None:
    """plain / target / eval / shadow / attack の5列横並びプレビューを保存する。"""
    columns: list[tuple[str, DecorationSpec | None]] = [
        ("plain", None),
        ("target", config.target_train_decoration),
        ("eval", config.eval_decoration),
        ("shadow", config.shadow_decoration),
        ("attack", config.attack_decoration),
    ]

    images = [
        apply_decoration_preview(builder, spec, original) for _, spec in columns
    ]
    width, height = original.size
    combined = Image.new("RGB", (width * len(images), height))
    for i, img in enumerate(images):
        combined.paste(img, (i * width, 0))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    combined.save(output_path)
    logger.info("Decoration preview saved: %s", output_path)
