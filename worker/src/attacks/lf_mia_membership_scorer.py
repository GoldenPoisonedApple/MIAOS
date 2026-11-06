"""
LF_MIA 系用メンバシップ推定（統計系）。

シャドー IN/OUT ペアの特徴 (n_pairs, C) から対角化された重みとバイアスを推定し、
ターゲット特徴 (C,) に対して sigmoid(w·x + b) でメンバシップ確率を返す。
ニューラル AttackNet 経路は LF_MIA 本体に残す。
"""

from __future__ import annotations

import numpy as np


# hyperparameters.membership_scorer で指定する値
MEMBERSHIP_SCORER_NEURAL = "neural"
MEMBERSHIP_SCORER_DIAGONAL_LDA = "diagonal_lda"

VALID_MEMBERSHIP_SCORERS = frozenset({
	MEMBERSHIP_SCORER_NEURAL,
	MEMBERSHIP_SCORER_DIAGONAL_LDA,
})

DEFAULT_DIAGONAL_LDA_REG_LAMBDA = 1e-3


class DiagonalLdaMembershipScorer:
	"""
	シャドーペアの差分 IN−OUT に対する対角 LDA 風の線形スコア。

	diff の次元ごとに平均/（分散+λ）で重みを取り、全ペアの中点平均を通る超平面上にバイアスを置く。
	"""

	def __init__(self, reg_lambda: float = DEFAULT_DIAGONAL_LDA_REG_LAMBDA) -> None:
		self.reg_lambda = float(reg_lambda)
		self._w: np.ndarray | None = None
		self._b: float | None = None

	def fit(self, in_feats: np.ndarray, out_feats: np.ndarray) -> None:
		"""in_feats, out_feats: (n_pairs, C)"""
		in_feats = np.asarray(in_feats, dtype=np.float64)
		out_feats = np.asarray(out_feats, dtype=np.float64)
		if in_feats.shape != out_feats.shape:
			raise ValueError("in_feats and out_feats must have the same shape")
		if in_feats.ndim != 2:
			raise ValueError("in_feats and out_feats must be 2D (n_pairs, C)")
		diffs = in_feats - out_feats
		midpoints = 0.5 * (in_feats + out_feats)
		mean_diff = diffs.mean(axis=0)
		n_pairs = diffs.shape[0]
		# n_pairs==1 のとき ddof=1 の分散は定義不能なので正則項のみとする
		if n_pairs <= 1:
			var_diff = np.full_like(mean_diff, self.reg_lambda, dtype=np.float64)
		else:
			var_diff = diffs.var(axis=0, ddof=1) + self.reg_lambda
		self._w = mean_diff / var_diff
		self._b = -float(np.dot(self._w, midpoints.mean(axis=0)))

	def score_target(self, target_feat: np.ndarray) -> float:
		"""target_feat: (C,) メンバーシップ確率 [0,1]"""
		if self._w is None or self._b is None:
			raise RuntimeError("DiagonalLdaMembershipScorer.fit must be called before score_target")
		x = np.asarray(target_feat, dtype=np.float64).reshape(-1)
		if x.shape != self._w.shape:
			raise ValueError(
				f"target_feat dim {x.shape} does not match w dim {self._w.shape}"
			)
		logit = float(np.dot(self._w, x) + self._b)
		return float(1.0 / (1.0 + np.exp(-logit)))

	@property
	def w(self) -> np.ndarray | None:
		return self._w

	@property
	def b(self) -> float | None:
		return self._b
