from dataclasses import dataclass
from typing import Any

import numpy as np

from src.data.decorations.config import DecorationSpec
from src.utils.hp_parsing import parse_bool

# IN シャドーの装飾適用率スイープの段階（ペア i には i % 10 番目を割り当てる）
SHADOW_IN_FRACTIONS: tuple[float, ...] = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1)


@dataclass(frozen=True)
class ShadowFractionSweep:
	"""
	IN シャドーの装飾適用率の割り当て方。
	enabled=False: 全 IN シャドーに shadow_decoration.fraction をそのまま使う
	enabled=True: shadow_decoration.fraction を無視し、SHADOW_IN_FRACTIONS を各段階同数ずつ割り当てる
	"""

	enabled: bool = False

	@classmethod
	def from_hyperparameters(cls, hp: dict[str, Any] | None) -> "ShadowFractionSweep":
		"""shadow_fraction_sweep: false（デフォルト）| true（文字列も可）"""
		if not hp:
			return cls()
		return cls(enabled=parse_bool(hp.get("shadow_fraction_sweep", False), "shadow_fraction_sweep"))

	def in_fractions(self, n_pairs: int, base_spec: DecorationSpec | None) -> np.ndarray:
		"""ペアごとの IN シャドーの適用率 (n_pairs,)。base_spec=None は装飾なし（適用率 0）"""
		if not self.enabled:
			fraction = 0.0 if base_spec is None else base_spec.apply.fraction
			return np.full(n_pairs, fraction, dtype=np.float64)
		if base_spec is None:
			raise ValueError("shadow_fraction_sweep=true requires shadow_decoration")
		num_levels = len(SHADOW_IN_FRACTIONS)
		if n_pairs % num_levels != 0:
			raise ValueError(
				f"shadow_fraction_sweep=true requires n_pairs (num_shadow_models / 2) to be a multiple "
				f"of {num_levels}, got n_pairs={n_pairs}"
			)
		return np.array([SHADOW_IN_FRACTIONS[i % num_levels] for i in range(n_pairs)], dtype=np.float64)
