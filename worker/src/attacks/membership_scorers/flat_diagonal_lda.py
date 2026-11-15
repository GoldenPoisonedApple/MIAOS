"""
LF_MIA 系用メンバシップ推定（統計系・K 枚結合）。

シャドー IN/OUT ペアの特徴 (n_pairs, K, C) を (n_pairs, K*C) に平坦化し、
(k, c) ごとに独立な重みを持つ対角 LDA 風の線形スコアを推定する。
ターゲット特徴 (K, C) に対しては K 枚を結合したスカラーの logit を返す。
"""

from typing import Any

import numpy as np

from src.attacks.membership_scorers.base import MembershipScore, ScoreScale, ShadowPairFeatures
from src.attacks.membership_scorers.class_selection import (
	DEFAULT_SIGNIFICANT_CLASS_SELECTION,
	ClassMask,
	SignificantClassSelection,
	select_significant_classes,
)
from src.attacks.membership_scorers.diagonal_lda import (
	DEFAULT_DIAGONAL_LDA_REG_LAMBDA,
	DiagonalVariance,
	fit_diagonal_linear,
)


DEFAULT_FLAT_DIAGONAL_LDA_VARIANCE = DiagonalVariance.WITHIN_CLASS


class FlatDiagonalLdaMembershipScorer:
	"""
	(k, c) を独立な次元として扱う対角 LDA 風の線形スコア。

	diagonal_lda は全 k で重みを共有する（K 平均してから学習する）特殊ケースに当たる。
	本クラスは画像 k ごとに「どのクラスがどれだけ安定して IN/OUT で動くか」を個別に重み付けする。
	画像間の相関は無視するため |logit| は K に比例して大きくなる（順位付けにのみ用いる）。
	分母の分散は variance で選ぶ（既定は within_class。none では分散で割らず平均差のみ）。
	class_selection で shadow_pair 分析で有意なクラス c の (k, c) のみに重みを持たせられる（既定は全クラス）。
	"""

	name = "flat_diagonal_lda"
	score_scale = ScoreScale.LOG_ODDS

	def __init__(
		self,
		reg_lambda: float = DEFAULT_DIAGONAL_LDA_REG_LAMBDA,
		variance: DiagonalVariance = DEFAULT_FLAT_DIAGONAL_LDA_VARIANCE,
		class_selection: SignificantClassSelection = DEFAULT_SIGNIFICANT_CLASS_SELECTION,
	) -> None:
		self.reg_lambda = float(reg_lambda)
		self.variance = DiagonalVariance(variance)
		self.class_selection = SignificantClassSelection(class_selection)
		# 重み (K, C) とバイアス
		self._w: np.ndarray | None = None
		self._b: float | None = None
		self._class_mask: ClassMask | None = None

	def fit(self, features: ShadowPairFeatures) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。(k, c) を独立な次元として平坦化する。"""
		in_feats = np.asarray(features.in_feats, dtype=np.float64)
		out_feats = np.asarray(features.out_feats, dtype=np.float64)
		if in_feats.shape != out_feats.shape:
			raise ValueError("in_feats and out_feats must have the same shape")
		if in_feats.ndim != 3:
			raise ValueError("in_feats and out_feats must be 3D (n_pairs, K, C)")

		n_pairs, num_images, num_classes = in_feats.shape
		# 平坦化: (n_pairs, K, C) -> (n_pairs, K*C)
		in_flat = in_feats.reshape(n_pairs, -1)
		out_flat = out_feats.reshape(n_pairs, -1)
		# 使うクラスの選択（既定は全クラス）。クラス単位の判定を全画像 k に広げて平坦化する
		self._class_mask = select_significant_classes(in_feats, out_feats, self.class_selection)
		flat_mask = self._class_mask.broadcast(num_images).reshape(-1)
		w, b = fit_diagonal_linear(in_flat, out_flat, self.reg_lambda, self.variance, flat_mask)
		# 重みを (K, C) に戻して保持する（画像ごとの寄与を計算するため）
		self._w = w.reshape(num_images, num_classes)
		self._b = b

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: K 枚を結合した logit, per_image: (K,) 画像ごとの寄与（和が value）"""
		if self._w is None or self._b is None:
			raise RuntimeError("FlatDiagonalLdaMembershipScorer.fit must be called before score")
		x = np.asarray(feats, dtype=np.float64)
		if x.shape != self._w.shape:
			raise ValueError(f"feats shape {x.shape} does not match {self._w.shape}")

		num_images = self._w.shape[0]
		# 画像ごとの寄与: w_k·x_k + b/K（バイアスは K 枚に等分し、和が w·vec(x) + b になるようにする）
		contrib = (x * self._w).sum(axis=1) + self._b / num_images
		return MembershipScore(value=float(contrib.sum()), per_image=contrib)

	def diagnostics(self) -> dict[str, Any]:
		if self._w is None or self._b is None or self._class_mask is None:
			return {}
		return {
			**self._class_mask.diagnostics(),
			"flat_diagonal_lda_reg_lambda": self.reg_lambda,
			"flat_diagonal_lda_variance": self.variance.value,
			"flat_diagonal_lda_w_norm": float(np.linalg.norm(self._w)),
			"flat_diagonal_lda_b": self._b,
			# どの画像の重みが効いているかを見るための画像ごとの重みノルム (K,)
			"flat_diagonal_lda_w_norm_per_image": np.linalg.norm(self._w, axis=1).tolist(),
		}
