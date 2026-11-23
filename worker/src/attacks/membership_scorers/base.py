from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

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


@dataclass(frozen=True)
class ShadowPairFeatures:
	"""
	シャドー IN/OUT ペアの特徴。in_feats, out_feats: (n_pairs, K, C)。分割はペア単位で行う。
	in_fractions: (n_pairs,) 各ペアの IN シャドーの装飾適用率（OUT シャドーは常に 0）
	"""

	in_feats: np.ndarray
	out_feats: np.ndarray
	in_fractions: np.ndarray

	def __post_init__(self) -> None:
		if self.in_feats.ndim != 3 or self.in_feats.shape != self.out_feats.shape:
			raise ValueError(
				f"in_feats / out_feats must have the same (n_pairs, K, C) shape, "
				f"got {self.in_feats.shape} / {self.out_feats.shape}"
			)
		if self.in_fractions.shape != (self.n_pairs,):
			raise ValueError(
				f"in_fractions must have shape ({self.n_pairs},), got {self.in_fractions.shape}"
			)

	@classmethod
	def uniform(
		cls, in_feats: np.ndarray, out_feats: np.ndarray, fraction: float = 1.0
	) -> "ShadowPairFeatures":
		"""全ペアの IN シャドーが同じ適用率のペア特徴"""
		return cls(
			in_feats=in_feats,
			out_feats=out_feats,
			in_fractions=np.full(in_feats.shape[0], fraction, dtype=np.float64),
		)

	@property
	def n_pairs(self) -> int:
		return int(self.in_feats.shape[0])

	# 1shadowの合成画像枚数
	@property
	def images_per_shadow(self) -> int:
		return int(self.in_feats.shape[1])

	@property
	def num_classes(self) -> int:
		return int(self.in_feats.shape[2])

	@property
	def is_stratified(self) -> bool:
		"""IN シャドーの適用率が 2 種類以上あるか（ペア分割の層化が必要か）"""
		return np.unique(self.in_fractions).size > 1


class MembershipScorer(Protocol):
	"""
	シャドー IN/OUT ペアの特徴から学習し、ターゲット特徴のメンバシップスコアを返す攻撃モデル。

	特徴の形状:
		fit:   features.in_feats, features.out_feats は (n_pairs, K, C)。K はプローブ画像枚数（LF_MIA では 1）
		score: feats は (K, C)、戻り値は MembershipScore（value はスカラー、per_image は (K,)）
	score_scale: score が返す値のスケール
	"""

	name: str
	score_scale: ScoreScale

	def fit(self, features: ShadowPairFeatures) -> None: ...

	def score(self, feats: np.ndarray) -> MembershipScore: ...

	def diagnostics(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class DecisionAnalysisData:
	"""
	学習済み判別モデルの可視化の入力（scorer に依存しない）。
	unit: 1 点の単位（image: 画像単位 / shadow: シャドー・ターゲット単位）
	shadow_x: (N, D) シャドーのサンプル, shadow_y: (N,) IN=1 / OUT=0,
	shadow_logit: (N,) 学習に使っていない fold のモデルによる較正後 logit（out-of-fold）
	target_x: (M, D) ターゲットのサンプル, target_fraction: (M,) ターゲットの装飾適用率,
	target_logit: (M,) fold モデルの較正後 logit の平均
	"""

	scorer_name: str
	unit: str
	shadow_x: np.ndarray
	shadow_y: np.ndarray
	shadow_logit: np.ndarray
	target_x: np.ndarray
	target_fraction: np.ndarray
	target_logit: np.ndarray


@runtime_checkable
class DecisionAnalyzable(Protocol):
	"""fit 後に判別モデルの可視化データを提供できる scorer。"""

	def decision_analysis(
		self, target_feats: np.ndarray, target_fractions: np.ndarray
	) -> DecisionAnalysisData:
		"""target_feats: (T, K, C), target_fractions: (T,)"""
		...
