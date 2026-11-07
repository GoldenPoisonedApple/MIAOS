from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

import numpy as np


class ScoreScale(str, Enum):
	"""攻撃スコアのスケール。閾値系の指標や分布図の横軸の単位を判別するために使う。"""

	# IN 確率 [0, 1]
	PROBABILITY = "probability"
	# 対数オッズ（logit / 対数尤度比）。実数全体
	LOG_ODDS = "log_odds"


@dataclass(frozen=True)
class MembershipScore:
	"""
	1 ターゲットモデル分の攻撃スコア。

	value: スコアラーが K 枚分を集約した最終スコア（大きいほど IN）
	per_image: 画像ごとのスコアまたは寄与 (K,)。集約方法（平均 / 和）はスコアラーの責務
	"""

	value: float
	per_image: np.ndarray

	@property
	def per_image_var(self) -> float:
		"""画像ごとのスコアの標本分散（K=1 では unbiased 分散が NaN になるため 0.0 とする）"""
		if self.per_image.size < 2:
			return 0.0
		return float(np.var(self.per_image, ddof=1))


class MembershipScorer(Protocol):
	"""
	シャドー IN/OUT ペアの特徴から学習し、ターゲット特徴のメンバシップスコアを返す攻撃モデル。

	特徴の形状:
		fit:   in_feats, out_feats は (n_pairs, K, C)。K はプローブ画像枚数（LF_MIA では 1）
		score: feats は (K, C)、戻り値は MembershipScore（value はスカラー、per_image は (K,)）
	score_scale: score が返す値のスケール
	"""

	name: str
	score_scale: ScoreScale

	def fit(self, in_feats: np.ndarray, out_feats: np.ndarray) -> None: ...

	def score(self, feats: np.ndarray) -> MembershipScore: ...

	def diagnostics(self) -> dict[str, Any]: ...
