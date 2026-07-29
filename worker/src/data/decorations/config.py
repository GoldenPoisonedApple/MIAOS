from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.server_client.models import CreateExperimentRequest
from src.server_client.types import UNSET

DecorationType = Literal["watermark", "display_mask"]


@dataclass(frozen=True)
class DecorationApplyPolicy:
    fraction: float  # 0.0–1.0, 省略時 1.0
    seed_offset: int  # 省略時 0


@dataclass(frozen=True)
class WatermarkDecorationSpec:
    filter_id: str
    apply: DecorationApplyPolicy
    type: Literal["watermark"] = "watermark"


@dataclass(frozen=True)
class DisplayMaskDecorationSpec:
    width: int
    height: int
    x: int
    y: int
    apply: DecorationApplyPolicy
    type: Literal["display_mask"] = "display_mask"


DecorationSpec = WatermarkDecorationSpec | DisplayMaskDecorationSpec


@dataclass(frozen=True)
class DecorationConfig:
    """hyperparameters から読み取った装飾設定"""

    # 評価用
    eval_decoration: DecorationSpec | None
    # ターゲット用
    target_train_decoration: DecorationSpec | None
    # 攻撃用（将来対応。現行 pipeline では未使用）
    attack_decoration: DecorationSpec | None = None

    # 設定のパース
    # cls: selfのClass版
    # 評価用とターゲット用の設定をパース
    @classmethod
    def from_request(cls, settings: CreateExperimentRequest) -> DecorationConfig:
        hyperparameters = settings.hyperparameters
        if hyperparameters is UNSET or hyperparameters is None:
            return cls(
                eval_decoration=None,
                target_train_decoration=None,
                attack_decoration=None,
            )

        hp = hyperparameters.to_dict()
        return cls(
            # 評価用
            eval_decoration=cls._parse_decoration(hp.get("eval_decoration")),
            # ターゲット用
            target_train_decoration=cls._parse_decoration(
                hp.get("target_train_decoration")
            ),
            # 攻撃用
            attack_decoration=cls._parse_decoration(hp.get("attack_decoration")),
        )

    # デコレーションの型バリデーション
    @classmethod
    def _parse_decoration(cls, raw: Any) -> DecorationSpec | None:
        if raw is None:
            return None
        if isinstance(raw, list):
            raise ValueError(
                "decoration must be a single object; "
                "use eval_decoration / target_train_decoration instead of a list"
            )
        if not isinstance(raw, dict):
            raise ValueError("decoration must be an object")
        return cls._parse_spec(raw)

    # 適用ポリシーバリデーション 適合割合
    @classmethod
    def _parse_apply_policy(cls, data: dict[str, Any]) -> DecorationApplyPolicy:
        fraction = float(data.get("fraction", 1.0))
        if not 0.0 <= fraction <= 1.0:
            raise ValueError("decoration fraction must be between 0.0 and 1.0")
        seed_offset = int(data.get("seed_offset", 0))
        return DecorationApplyPolicy(fraction=fraction, seed_offset=seed_offset)

    # デコレーションのパース
    @classmethod
    def _parse_spec(cls, data: dict[str, Any]) -> DecorationSpec:
        decoration_type = data.get("type")
        # 適用ポリシーバリデーション
        apply = cls._parse_apply_policy(data)
        # ウォーターマーク
        if decoration_type == "watermark":
            filter_id = data.get("filter_id")
            if not filter_id:
                raise ValueError("watermark decoration requires filter_id")
            return WatermarkDecorationSpec(
                filter_id=str(filter_id),
                apply=apply,
            )
        # 部分表示
        if decoration_type == "display_mask":
            width = int(data.get("width", 16))
            height = int(data.get("height", 16))
            x, y = cls._parse_position(data)
            return DisplayMaskDecorationSpec(
                width=width,
                height=height,
                x=x,
                y=y,
                apply=apply,
            )
        raise ValueError(f"Unknown decoration type: {decoration_type!r}")

    # 部分表示用 座標バリデーション
    @classmethod
    def _parse_position(cls, data: dict[str, Any]) -> tuple[int, int]:
        """position は表示領域左上の [x, y] 座標（画像左上基準）"""
        position = data.get("position")
        if position is not None:
            if isinstance(position, (list, tuple)) and len(position) == 2:
                return int(position[0]), int(position[1])
            if isinstance(position, dict):
                if "x" not in position or "y" not in position:
                    raise ValueError("position object requires x and y")
                return int(position["x"]), int(position["y"])
            raise ValueError("position must be [x, y] or {x, y}")

        if "x" in data or "y" in data:
            return int(data.get("x", 0)), int(data.get("y", 0))

        return 0, 0
