from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from src.server_client.models import CreateExperimentRequest
from src.server_client.types import UNSET

SPLIT_NAMES = frozenset({"target_train", "target_test", "shadow_train", "shadow_test"})

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


@dataclass(frozen=True)
class WatermarkConfig:
    """透かし設定の値オブジェクト"""

    enabled: bool
    mask_path: str
    color: tuple[int, int, int]
    opacity: float
    position: tuple[int, int]
    apply_to: frozenset[str]
    fraction: float
    seed_offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mask_path": self.mask_path,
            "color": list(self.color),
            "opacity": self.opacity,
            "position": list(self.position),
            "apply_to": sorted(self.apply_to),
            "fraction": self.fraction,
            "seed_offset": self.seed_offset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatermarkConfig:
        apply_to = data.get("apply_to", [])
        if isinstance(apply_to, str):
            apply_to = [apply_to]
        apply_to_set = frozenset(apply_to)
        invalid = apply_to_set - SPLIT_NAMES
        if invalid:
            raise ValueError(f"Invalid apply_to splits: {sorted(invalid)}")

        color = tuple(data.get("color", [255, 255, 255]))
        if len(color) != 3:
            raise ValueError("color must be [R, G, B]")

        position = tuple(data.get("position", [0, 0]))
        if len(position) != 2:
            raise ValueError("position must be [x, y]")

        opacity = float(data.get("opacity", 0.6))
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")

        fraction = float(data.get("fraction", 1.0))
        if not 0.0 <= fraction <= 1.0:
            raise ValueError("fraction must be between 0.0 and 1.0")

        mask_path = data.get("mask_path")
        if not mask_path:
            raise ValueError("mask_path is required when watermark is enabled")

        return cls(
            enabled=bool(data.get("enabled", False)),
            mask_path=str(mask_path),
            color=(int(color[0]), int(color[1]), int(color[2])),
            opacity=opacity,
            position=(int(position[0]), int(position[1])),
            apply_to=apply_to_set,
            fraction=fraction,
            seed_offset=int(data.get("seed_offset", 0)),
        )

    @classmethod
    def from_hyperparameters(
        cls, settings: CreateExperimentRequest
    ) -> WatermarkConfig | None:
        hyperparameters = settings.hyperparameters
        if hyperparameters is UNSET or hyperparameters is None:
            return None

        watermark_data = hyperparameters.additional_properties.get("watermark")
        if not watermark_data:
            return None

        config = cls.from_dict(watermark_data)
        if not config.enabled:
            return None
        return config

    def resolve_mask_path(self, assigned_model_path: str | None = None) -> str:
        """マスクファイルパスを解決する（優先度: ベース実験 > プロジェクトルート > 絶対パス）"""
        candidates: list[str] = []
        if assigned_model_path is not None:
            candidates.append(os.path.join(assigned_model_path, self.mask_path))
        candidates.append(os.path.join(PROJECT_ROOT, self.mask_path))
        if os.path.isabs(self.mask_path):
            candidates.append(self.mask_path)

        for path in candidates:
            if os.path.isfile(path):
                return path

        raise FileNotFoundError(
            f"Watermark mask not found: {self.mask_path} "
            f"(searched: {', '.join(candidates)})"
        )
