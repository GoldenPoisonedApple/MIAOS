from typing import Any, Protocol

import numpy as np


class MembershipScorer(Protocol):
	"""
	シャドー IN/OUT ペアの特徴から学習し、ターゲット特徴の IN 確率を返す攻撃モデル。

	特徴の形状:
		fit:   in_feats, out_feats は (n_pairs, K, C)。K はプローブ画像枚数（LF_MIA では 1）
		score: feats は (K, C)、戻り値は (K,) の IN 確率
	"""

	name: str

	def fit(self, in_feats: np.ndarray, out_feats: np.ndarray) -> None: ...

	def score(self, feats: np.ndarray) -> np.ndarray: ...

	def diagnostics(self) -> dict[str, Any]: ...
