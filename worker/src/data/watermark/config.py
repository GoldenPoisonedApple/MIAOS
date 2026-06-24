from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.server_client.models import CreateExperimentRequest
from src.server_client.types import UNSET

SPLIT_NAMES = frozenset({"target_train", "target_test", "shadow_train", "shadow_test"})


@dataclass(frozen=True)
class WatermarkConfig:
    """透かし設定の値オブジェクト"""

    enabled: bool
    filter_id: str
    apply: dict[str, float]
    seed_offset: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "filter_id": self.filter_id,
            "apply": dict(self.apply),
            "seed_offset": self.seed_offset,
        }

    def active_splits(self) -> list[tuple[str, float]]:
        """値 > 0 の分割を (名前, 割合) のリストで返す（名前はソート済み）"""
        return sorted(
            (name, fraction) for name, fraction in self.apply.items() if fraction > 0.0
        )

    def fraction_for(self, split_name: str) -> float:
        return self.apply.get(split_name, 0.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatermarkConfig:
        apply_raw = data.get("apply", {})
        if not isinstance(apply_raw, dict):
            raise ValueError("apply must be an object")

        apply: dict[str, float] = {}
        for key, value in apply_raw.items():
            if key not in SPLIT_NAMES:
                raise ValueError(f"Invalid apply split: {key}")
            fraction = float(value)
            if not 0.0 <= fraction <= 1.0:
                raise ValueError(f"apply.{key} must be between 0.0 and 1.0")
            if fraction > 0.0:
                apply[key] = fraction

        filter_id = data.get("filter_id")
        if not filter_id:
            raise ValueError("filter_id is required when watermark is enabled")

        enabled = bool(data.get("enabled", False))
        if enabled and not apply:
            raise ValueError("apply must contain at least one split with fraction > 0")

        return cls(
            enabled=enabled,
            filter_id=str(filter_id),
            apply=apply,
            seed_offset=int(data.get("seed_offset", 0)),
        )

    @classmethod
    def from_request(cls, settings: CreateExperimentRequest) -> WatermarkConfig | None:
        watermark = settings.watermark
        if watermark is UNSET or watermark is None:
            return None

        watermark_data = watermark.additional_properties
        if not watermark_data:
            return None

        config = cls.from_dict(watermark_data)
        if not config.enabled:
            return None
        return config
