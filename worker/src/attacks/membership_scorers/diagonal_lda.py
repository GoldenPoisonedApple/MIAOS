"""
LF_MIA 系用メンバシップ推定（統計系）。

シャドー IN/OUT ペアの特徴 (n_pairs, C) から対角化された重みとバイアスを推定し、
ターゲット特徴 (C,) に対して線形スコア w·x + b（logit）を返す。
"""

from enum import Enum
from typing import Any

import numpy as np

from src.attacks.membership_scorers.base import MembershipScore, ScoreScale


DEFAULT_DIAGONAL_LDA_REG_LAMBDA = 1e-3


class DiagonalVariance(str, Enum):
	"""対角線形スコアの重みの分母に使う分散。"""

	# ペア差分 IN−OUT の分散。データ分割由来の分散はペア内で相殺される
	PAIR_DIFF = "pair_diff"
	# クラス内分散（IN/OUT それぞれの分散のプール）。ペアを持たない単体モデルのノイズに対応する
	WITHIN_CLASS = "within_class"


def fit_diagonal_linear(
	in_x: np.ndarray,
	out_x: np.ndarray,
	reg_lambda: float,
	variance: DiagonalVariance,
) -> tuple[np.ndarray, float]:
	"""
	シャドー IN/OUT ペアの特徴から対角 LDA 風の重みとバイアスを推定する。

	diff の次元ごとに平均/（分散+λ）で重みを取り、全ペアの中点平均を通る超平面上にバイアスを置く。
	クラス間の相関は無視する（対角近似）。
	Args:
			in_x, out_x: (n_pairs, D)。同じ行が同じペア
			reg_lambda: 分散に加える正則化項
			variance: 分母に使う分散の種類
	Returns:
			w: (D,) 重み
			b: バイアス（スカラー）
	"""
	if in_x.shape != out_x.shape or in_x.ndim != 2:
		raise ValueError("in_x and out_x must be 2D arrays of the same shape (n_pairs, D)")
	# ペア差分
	diffs = in_x - out_x		# (n_pairs, D)
	mean_diff = diffs.mean(axis=0) 	# (D,) 全ペア差分の平均
	# ペア中点
	midpoints = 0.5 * (in_x + out_x)	# (n_pairs, D)
	mean_midpoints = midpoints.mean(axis=0) # (D,) 全ペア中点の平均
	# 分散 (D,)
	# reg_lambda: 正則化項 (L2正則化)
	# n_pairs==1 のとき ddof=1 の分散は定義不能なので正則項のみとする
	n_pairs = diffs.shape[0]
	if n_pairs <= 1:
		var = np.full_like(mean_diff, reg_lambda, dtype=np.float64)
	elif variance == DiagonalVariance.PAIR_DIFF:
		# ペア差分の分散
		var = diffs.var(axis=0, ddof=1) + reg_lambda
	else:
		# クラス内分散: IN/OUT の分散の平均
		var = 0.5 * (in_x.var(axis=0, ddof=1) + out_x.var(axis=0, ddof=1)) + reg_lambda
	# 重み (D,)
	w = mean_diff / var
	# バイアス: IN/OUT境界(ペア中点)を通る超平面の切片(スカラー), wm + b = 0 より b = -wm
	b = -float(np.dot(w, mean_midpoints))
	return w, b


class DiagonalLdaMembershipScorer:
	"""
	シャドーペアの差分 IN−OUT に対する対角 LDA 風の線形スコア。

	diff の次元ごとに平均/（分散+λ）で重みを取り、全ペアの中点平均を通る超平面上にバイアスを置く。
	クラス間の相関は無視する（対角近似）。
	K 枚は平均してから学習し、スコアは画像ごとの logit の平均とする。
	"""

	name = "diagonal_lda"
	score_scale = ScoreScale.LOG_ODDS

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
		# 重みとバイアス: ペア差分の分散を分母とする（従来どおり）
		self._w, self._b = fit_diagonal_linear(
			in_pair, out_pair, self.reg_lambda, DiagonalVariance.PAIR_DIFF
		)

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: 画像ごとの logit の平均, per_image: (K,) logit"""
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
		# シグモイド関数は通さず logit のまま返す
		# 確率に変換すると |logit| が大きいとき 0/1 に飽和し、ROC で同点が生じるため
		# 線形なので logit の平均 = K 平均した特徴の logit となり、学習時（K 平均）と整合する
		return MembershipScore(value=float(logits.mean()), per_image=logits)

	def diagnostics(self) -> dict[str, Any]:
		if self._w is None or self._b is None:
			return {}
		return {
			"diagonal_lda_reg_lambda": self.reg_lambda,
			"diagonal_lda_w_norm": float(np.linalg.norm(self._w)),
			"diagonal_lda_b": self._b,
		}
