from __future__ import annotations

import numpy as np

from src.data.decorations.apply_policy import (
    decoration_random_state,
    select_indices_by_fraction,
)
from src.data.decorations.config import (
    DecorationSpec,
    DisplayMaskDecorationSpec,
    WatermarkDecorationSpec,
)
from src.data.decorations.display_mask.decorator import DisplayMaskDecorator
from src.data.decorations.fractional import FractionalDecorator
from src.data.decorations.protocol import SampleDecorator
from src.data.decorations.watermark.decorator import WatermarkDecorator
from src.data.decorations.watermark.loader import WatermarkLoader


class SampleDecoratorBuilder:
    """DecorationSpec から SampleDecorator を構築する"""

    def __init__(self, *, experiment_seed: int):
        self._experiment_seed = experiment_seed
        self._watermark_loader: WatermarkLoader | None = None

    def get_watermark_loader(self) -> WatermarkLoader:
        """watermark loaderを取得"""
        # キャッシュにない場合は WatermarkLoader を作成
        if self._watermark_loader is None:
            self._watermark_loader = WatermarkLoader()
        return self._watermark_loader

    # 装飾の構築
    # *: *移行はキーワード付き引数のみしか受け取れない
    def build(
        self,
        *,
        spec: DecorationSpec | None,
        pool_indices: np.ndarray,
    ) -> SampleDecorator | None:
        if spec is None:
            return None

        # シード計算
        random_state = decoration_random_state(
            self._experiment_seed, spec.apply.seed_offset
        )
        # 装飾適応インデックス計算
        indices = select_indices_by_fraction(
            pool_indices, spec.apply.fraction, random_state
        )
        if not indices:
            return None

        # 適用情報確定
        if isinstance(spec, WatermarkDecorationSpec):
            inner = WatermarkDecorator(
                # 透かし変換オブジェクト取得
                self.get_watermark_loader().get(spec.filter_id)
            )
        elif isinstance(spec, DisplayMaskDecorationSpec):
            # 表示領域マスクオブジェクト作成
            inner = DisplayMaskDecorator(
                width=spec.width,
                height=spec.height,
                x=spec.x,
                y=spec.y,
            )
        else:
            raise ValueError(f"Unknown decoration spec: {spec!r}")

        # 適用情報確定
        return FractionalDecorator(inner, indices=indices)
