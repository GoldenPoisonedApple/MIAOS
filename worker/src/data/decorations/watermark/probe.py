from __future__ import annotations

import logging
import os

import torch
from PIL import Image
from torch.utils.data import DataLoader, TensorDataset

from src.data.decorations.watermark.loader import WatermarkLoader

logger = logging.getLogger(__name__)


def build_probe_pil(
    loader: WatermarkLoader,
    filter_id: str,
    variant: str = "on_black",
) -> Image.Image:
    """透かしフィルタ1枚を probe 用 PIL として返す"""
    if variant == "filter_rgb":
        return loader.get_filter_pil(filter_id)

    watermark = loader.get(filter_id)
    if variant == "on_black":
        base = Image.new("RGB", (32, 32), (0, 0, 0))
        return watermark(base)
    if variant == "on_gray":
        base = Image.new("RGB", (32, 32), (128, 128, 128))
        return watermark(base)

    raise ValueError(f"Unknown watermark probe variant: {variant}")


def save_comparison_preview(
    loader: WatermarkLoader,
    filter_id: str,
    original: Image.Image,
    output_path: str,
) -> None:
    """透かしあり/なしの比較画像を保存する"""
    watermark = loader.get(filter_id)
    watermarked = watermark(original)
    width, height = original.size
    combined = Image.new("RGB", (width * 2, height))
    combined.paste(original, (0, 0))
    combined.paste(watermarked, (width, 0))
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    combined.save(output_path)
    logger.info("Watermark preview saved: %s", output_path)


def build_probe_dataloader(
    transform,
    loader: WatermarkLoader,
    filter_id: str,
    variant: str = "on_black",
) -> tuple[DataLoader, str]:
    """透かし probe 1枚用 DataLoader（評価と同じ transform を適用）"""
    probe_pil = build_probe_pil(loader, filter_id, variant)
    tensor = transform(probe_pil).unsqueeze(0)
    dummy_label = torch.tensor([0], dtype=torch.long)
    data_loader = DataLoader(
        TensorDataset(tensor, dummy_label),
        batch_size=1,
        shuffle=False,
        num_workers=0,
    )
    return data_loader, variant
