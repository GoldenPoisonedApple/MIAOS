"""
LF_MIA 系用メンバシップ推定（統計系・K 枚結合）。

LiRA (Carlini et al., 2022) の尤度比検定を (K, C) 次元に拡張したもの。
(k, c) ごとに IN/OUT シャドーの正規分布を推定し、ターゲット特徴 (K, C) に対して
全次元の対数尤度比の和をスカラーのスコアとして返す。
特徴は logit_scaling 済み（LiRA と同じくガウス近似のための前処理）であることを前提とする。
"""

from enum import Enum
from typing import Any

import numpy as np

from src.attacks.membership_scorers.base import MembershipScore, ScoreScale


DEFAULT_GAUSSIAN_LR_VAR_FLOOR = 1e-3


class GaussianVariance(str, Enum):
	"""(k, c) ごとの正規分布の分散の推定方法。"""

	# IN/OUT で別々の分散（分散の変化も信号として使う。二次の決定境界）
	PER_CLASS = "per_class"
	# IN/OUT の分散の平均を共通に使う（シャドーが少ないとき向け。線形の決定境界）
	POOLED = "pooled"


DEFAULT_GAUSSIAN_LR_VARIANCE = GaussianVariance.PER_CLASS


class GaussianLrMembershipScorer:
	"""
	(k, c) ごとに IN/OUT の正規分布を推定し、対数尤度比の和をスコアとする。

	ペア構造は使わず、IN 群・OUT 群それぞれの分布を推定する（ターゲットもペアを持たない単体モデル）。
	次元間の相関は無視するため |score| は K*C に比例して大きくなる（順位付けにのみ用いる）。
	"""

	name = "gaussian_lr"
	score_scale = ScoreScale.LOG_ODDS

	def __init__(
		self,
		variance: GaussianVariance = DEFAULT_GAUSSIAN_LR_VARIANCE,
		var_floor: float = DEFAULT_GAUSSIAN_LR_VAR_FLOOR,
	) -> None:
		self.variance = GaussianVariance(variance)
		self.var_floor = float(var_floor)
		# (K, C) ごとの平均・分散
		self._mu_in: np.ndarray | None = None
		self._mu_out: np.ndarray | None = None
		self._var_in: np.ndarray | None = None
		self._var_out: np.ndarray | None = None
		# 分散が var_floor に張り付いた次元の割合（飽和の検知用）
		self._floored_ratio_in: float | None = None
		self._floored_ratio_out: float | None = None

	def fit(self, in_feats: np.ndarray, out_feats: np.ndarray) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)"""
		in_feats = np.asarray(in_feats, dtype=np.float64)
		out_feats = np.asarray(out_feats, dtype=np.float64)
		if in_feats.shape != out_feats.shape:
			raise ValueError("in_feats and out_feats must have the same shape")
		if in_feats.ndim != 3:
			raise ValueError("in_feats and out_feats must be 3D (n_pairs, K, C)")
		# (K, C) ごとの平均
		self._mu_in = in_feats.mean(axis=0)
		self._mu_out = out_feats.mean(axis=0)
		# (K, C) ごとの分散
		# n_pairs==1 のとき ddof=1 の分散は定義不能なので 0 とし、下限 var_floor のみとする
		n_pairs = in_feats.shape[0]
		if n_pairs <= 1:
			var_in = np.zeros_like(self._mu_in)
			var_out = np.zeros_like(self._mu_out)
		else:
			var_in = in_feats.var(axis=0, ddof=1)
			var_out = out_feats.var(axis=0, ddof=1)
		if self.variance == GaussianVariance.POOLED:
			# IN/OUT 共通の分散（クラス内分散のプール）
			var_in = var_out = 0.5 * (var_in + var_out)
		# logit が全モデルで飽和した次元は分散 0 になり得るので下限を設ける
		self._floored_ratio_in = float(np.mean(var_in < self.var_floor))
		self._floored_ratio_out = float(np.mean(var_out < self.var_floor))
		self._var_in = np.maximum(var_in, self.var_floor)
		self._var_out = np.maximum(var_out, self.var_floor)

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: 全次元の対数尤度比の和, per_image: (K,) 画像ごとの対数尤度比の和"""
		if (
			self._mu_in is None
			or self._mu_out is None
			or self._var_in is None
			or self._var_out is None
		):
			raise RuntimeError("GaussianLrMembershipScorer.fit must be called before score")
		x = np.asarray(feats, dtype=np.float64)
		if x.shape != self._mu_in.shape:
			raise ValueError(f"feats shape {x.shape} does not match {self._mu_in.shape}")

		# 正規分布の対数尤度（定数項 -0.5*log(2π) は IN/OUT で相殺されるため省略）
		ll_in = -0.5 * (np.log(self._var_in) + (x - self._mu_in) ** 2 / self._var_in)
		ll_out = -0.5 * (np.log(self._var_out) + (x - self._mu_out) ** 2 / self._var_out)
		# 対数尤度比 (K, C)
		llr = ll_in - ll_out
		# 画像ごとの対数尤度比の和 (K,)
		per_image = llr.sum(axis=1)
		return MembershipScore(value=float(per_image.sum()), per_image=per_image)

	def diagnostics(self) -> dict[str, Any]:
		if self._var_in is None or self._var_out is None:
			return {}
		return {
			"gaussian_lr_variance": self.variance.value,
			"gaussian_lr_var_floor": self.var_floor,
			"gaussian_lr_floored_ratio_in": self._floored_ratio_in,
			"gaussian_lr_floored_ratio_out": self._floored_ratio_out,
		}
