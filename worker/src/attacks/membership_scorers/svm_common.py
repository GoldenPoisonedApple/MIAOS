"""svm / flat_svm で共有する SVM の部品（探索空間・Platt 較正・fold モデル・OOF / アンサンブル logit）。"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import optuna
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.pipeline import Pipeline

from src.attacks.membership_scorers.base import DecisionAnalysisData, ShadowPairFeatures
from src.attacks.membership_scorers.pair_cv import (
	CvResult,
	LabeledSamples,
	PairCvOutcome,
	SampleLayout,
)

# 探索空間（固定）
C_RANGE: tuple[float, float] = (1e-4, 1e2)
# gamma = gamma_factor * (sklearn の gamma="scale" 相当の基準値)
GAMMA_FACTOR_RANGE: tuple[float, float] = (1e-3, 1e2)

# 可視化の単位（SampleLayout ごと）
DECISION_ANALYSIS_UNITS: dict[SampleLayout, str] = {
	SampleLayout.PER_IMAGE: "image",
	SampleLayout.FLAT: "shadow",
}


class SvmKernel(str, Enum):
	"""SVM のカーネル。"""

	# svm: LinearSVC / flat_svm: SVC(kernel="linear")
	LINEAR = "linear"
	# svm: Nystroem 近似の RBF 特徴写像 + LinearSVC（厳密な SVC は学習サンプル数に対して O(n^2)〜O(n^3) のため）
	# flat_svm: SVC(kernel="rbf")（サンプル数が n_pairs * 2 と少ないため厳密に解く）
	RBF = "rbf"


@dataclass(frozen=True)
class SvmParams:
	"""1 trial で探索するハイパーパラメータ。gamma_factor=None は linear カーネル。"""

	c: float
	gamma_factor: float | None

	@classmethod
	def from_trial(cls, trial: optuna.Trial, kernel: SvmKernel) -> "SvmParams":
		c = trial.suggest_float("C", *C_RANGE, log=True)
		# gamma は rbf のときだけ意味を持つ（条件付き探索）
		if kernel is SvmKernel.LINEAR:
			return cls(c=c, gamma_factor=None)
		return cls(c=c, gamma_factor=trial.suggest_float("gamma_factor", *GAMMA_FACTOR_RANGE, log=True))

	def to_dict(self) -> dict[str, Any]:
		return {"C": self.c, "gamma_factor": self.gamma_factor}


def scale_gamma(x: np.ndarray) -> float:
	"""sklearn の gamma="scale" と同じ基準値 1 / (n_features * X.var())。分散 0 では分母の分散を 1 とする"""
	var = float(x.var())
	return 1.0 / (x.shape[1] * (var if var > 0 else 1.0))


@dataclass(frozen=True)
class PlattScaling:
	"""
	decision_function f から IN の logit = a·f + b への Platt 較正（Platt, 1999）。
	目標値を正例 (N+ + 1)/(N+ + 2)、負例 1/(N- + 2) に平滑化して交差エントロピーを最小化する。
	平滑化により、較正データが完全に分離していても a が発散しない。
	"""

	a: float
	b: float

	@classmethod
	def fit(cls, decision: np.ndarray, y: np.ndarray) -> "PlattScaling":
		f = np.asarray(decision, dtype=np.float64)
		is_in = np.asarray(y) == 1
		n_pos = int(is_in.sum())
		n_neg = int(is_in.size - n_pos)
		t = np.where(is_in, (n_pos + 1.0) / (n_pos + 2.0), 1.0 / (n_neg + 2.0))

		def loss_and_grad(theta: np.ndarray) -> tuple[float, np.ndarray]:
			z = theta[0] * f + theta[1]
			# -[t log σ(z) + (1-t) log(1-σ(z))] = log(1 + e^z) - t z（数値安定な形）
			loss = float(np.mean(np.logaddexp(0.0, z) - t * z))
			residual = expit(z) - t
			return loss, np.array([np.mean(residual * f), np.mean(residual)])

		# 初期値: 傾き 0、切片は平滑化した事前確率の logit
		x0 = np.array([0.0, np.log((n_pos + 1.0) / (n_neg + 1.0))])
		result = minimize(loss_and_grad, x0, jac=True, method="L-BFGS-B")
		return cls(a=float(result.x[0]), b=float(result.x[1]))

	def logit(self, decision: np.ndarray) -> np.ndarray:
		return self.a * np.asarray(decision, dtype=np.float64) + self.b

	def proba(self, decision: np.ndarray) -> np.ndarray:
		return expit(self.logit(decision))


@dataclass(frozen=True)
class SvmFoldModel:
	"""1 fold 分の学習済みモデル（学習側で fit した SVM の Pipeline と、validation で fit した Platt 較正）。"""

	estimator: Pipeline
	platt: PlattScaling

	@property
	def best_iteration(self) -> None:
		return None

	def predict_logit(self, x: np.ndarray) -> np.ndarray:
		"""x: (N, D) → サンプルごとの Platt 較正後の IN の logit (N,)"""
		return self.platt.logit(self.estimator.decision_function(x))

	def predict_proba(self, x: np.ndarray) -> np.ndarray:
		"""x: (N, D) → サンプルごとの IN 確率 (N,)"""
		return self.platt.proba(self.estimator.decision_function(x))


def calibrate_fold(pipeline: Pipeline, train: LabeledSamples, val: LabeledSamples) -> SvmFoldModel:
	"""pipeline を学習側で fit し、validation の decision_function で Platt 較正する（学習と較正のデータは重ならない）"""
	pipeline.fit(train.x, train.y)
	platt = PlattScaling.fit(pipeline.decision_function(val.x), val.y)
	return SvmFoldModel(estimator=pipeline, platt=platt)


@dataclass(frozen=True)
class OofLogits:
	"""シャドーの out-of-fold logit。x: (N, D), y: (N,) IN=1 / OUT=0, logit: (N,)"""

	x: np.ndarray
	y: np.ndarray
	logit: np.ndarray


def oof_logits(
	outcome: PairCvOutcome[SvmParams, SvmFoldModel], data: ShadowPairFeatures
) -> OofLogits:
	"""各ペアを、そのペアがテストだった fold のモデルで評価する（各ペアはちょうど 1 回テスト fold に入る）"""
	xs: list[np.ndarray] = []
	ys: list[np.ndarray] = []
	logits: list[np.ndarray] = []
	for split, model in zip(outcome.splits, outcome.best.fold_models, strict=True):
		test = outcome.layout.to_samples(data, split.test_idx)
		xs.append(test.x)
		ys.append(test.y)
		logits.append(model.predict_logit(test.x))
	return OofLogits(x=np.concatenate(xs), y=np.concatenate(ys), logit=np.concatenate(logits))


def ensemble_logit(result: CvResult[SvmParams, SvmFoldModel], x: np.ndarray) -> np.ndarray:
	"""k 個の fold モデルの logit の平均（score が返す確率の平均とは厳密には一致しない）"""
	return np.mean([m.predict_logit(x) for m in result.fold_models], axis=0)


def build_decision_analysis(
	scorer_name: str,
	layout: SampleLayout,
	oof: OofLogits,
	result: CvResult[SvmParams, SvmFoldModel],
	target_feats: np.ndarray,
	target_fractions: np.ndarray,
) -> DecisionAnalysisData:
	"""target_feats: (T, K, C), target_fractions: (T,) → 可視化の入力（ターゲットは layout の単位に展開）"""
	target_x = np.concatenate([
		layout.flatten_target(np.asarray(f, dtype=np.float32)) for f in target_feats
	])
	# ターゲット 1 体あたりのサンプル数（PER_IMAGE: K, FLAT: 1）で適用率を複製する
	rows_per_target = target_x.shape[0] // len(target_feats)
	return DecisionAnalysisData(
		scorer_name=scorer_name,
		unit=DECISION_ANALYSIS_UNITS[layout],
		shadow_x=oof.x,
		shadow_y=oof.y,
		shadow_logit=oof.logit,
		target_x=target_x,
		target_fraction=np.repeat(np.asarray(target_fractions, dtype=np.float64), rows_per_target),
		target_logit=ensemble_logit(result, target_x),
	)
