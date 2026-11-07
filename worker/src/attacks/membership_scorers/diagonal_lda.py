"""
LF_MIA 系用メンバシップ推定（統計系）。

シャドー IN/OUT ペアの特徴 (n_pairs, C) から対角化された重みとバイアスを推定し、
ターゲット特徴 (C,) に対して sigmoid(w·x + b) でメンバシップ確率を返す。
"""

from typing import Any

import numpy as np


DEFAULT_DIAGONAL_LDA_REG_LAMBDA = 1e-3


class DiagonalLdaMembershipScorer:
	"""
	シャドーペアの差分 IN−OUT に対する対角 LDA 風の線形スコア。

	diff の次元ごとに平均/（分散+λ）で重みを取り、全ペアの中点平均を通る超平面上にバイアスを置く。
	クラス間の相関は無視する（対角近似）。
	"""

	name = "diagonal_lda"

	def __init__(self, reg_lambda: float = DEFAULT_DIAGONAL_LDA_REG_LAMBDA) -> None:
		self.reg_lambda = float(reg_lambda)
		self._w: np.ndarray | None = None
		self._b: float | None = None

	def fit(self, in_feats: np.ndarray, out_feats: np.ndarray) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。K 方向に平均してペアあたり 1 ベクトルにする。"""
		in_feats = np.asarray(in_feats, dtype=np.float64)
		out_feats = np.asarray(out_feats, dtype=np.float64)
		if in_feats.shape != out_feats.shape:
			raise ValueError("in_feats and out_feats must have the same shape")
		if in_feats.ndim != 3:
			raise ValueError("in_feats and out_feats must be 3D (n_pairs, K, C)")
		in_pair = in_feats.mean(axis=1)		# 全合成画像平均 (n_pairs, C)
		out_pair = out_feats.mean(axis=1)	# 全合成画像平均 (n_pairs, C)
		# ペア差分
		diffs = in_pair - out_pair		# (n_pairs, C)
		mean_diff = diffs.mean(axis=0) 	# (C,) 全ペア差分の平均
		# ペア中点
		midpoints = 0.5 * (in_pair + out_pair)	# (n_pairs, C)
		mean_midpoints = midpoints.mean(axis=0) # (C,) 全ペア中点の平均
		# ペア差分の分散 (C,)
		# reg_lambda: 正則化項 (L2正則化)
		# n_pairs==1 のとき ddof=1 の分散は定義不能なので正則項のみとする
		n_pairs = diffs.shape[0]
		if n_pairs <= 1:
			var_diff = np.full_like(mean_diff, self.reg_lambda, dtype=np.float64)
		else:
			var_diff = diffs.var(axis=0, ddof=1) + self.reg_lambda
		# 重み (C,)
		self._w = mean_diff / var_diff
		# バイアス: IN/OUT境界(ペア中点)を通る超平面の切片(スカラー), wm + b = 0 より b = -wm
		self._b = -float(np.dot(self._w, mean_midpoints))

	def score(self, feats: np.ndarray) -> np.ndarray:
		"""feats: (K, C) → (K,) メンバーシップ確率 [0,1]"""
		if self._w is None or self._b is None:
			raise RuntimeError("DiagonalLdaMembershipScorer.fit must be called before score")
		x = np.asarray(feats, dtype=np.float64)
		if x.ndim != 2 or x.shape[1] != self._w.shape[0]:
			raise ValueError(
				f"feats shape {x.shape} does not match (K, {self._w.shape[0]})"
			)
		# 線形スコア: xw + b
		# バイアスによって中間が0になっている
		logits = x @ self._w + self._b
		# シグモイド関数によって確率に変換
		return 1.0 / (1.0 + np.exp(-logits))

	def diagnostics(self) -> dict[str, Any]:
		if self._w is None or self._b is None:
			return {}
		return {
			"diagonal_lda_reg_lambda": self.reg_lambda,
			"diagonal_lda_w_norm": float(np.linalg.norm(self._w)),
			"diagonal_lda_b": self._b,
		}
