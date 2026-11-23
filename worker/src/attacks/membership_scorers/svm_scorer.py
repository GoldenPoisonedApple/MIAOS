import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import optuna
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.kernel_approximation import Nystroem
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

import src.core.config as cfg
from src.attacks.membership_scorers.base import MembershipScore, ScoreScale, ShadowPairFeatures
from src.attacks.membership_scorers.pair_cv import (
	CvResult,
	CvSettings,
	LabeledSamples,
	PairCvSearch,
)

# 探索空間（固定）
C_RANGE: tuple[float, float] = (1e-4, 1e2)
# gamma = gamma_factor * (sklearn の gamma="scale" 相当の基準値)
GAMMA_FACTOR_RANGE: tuple[float, float] = (1e-3, 1e2)

IN_LABEL: float = 1.0


class SvmKernel(str, Enum):
	"""SVM のカーネル。"""

	# LinearSVC
	LINEAR = "linear"
	# Nystroem 近似の RBF 特徴写像 + LinearSVC（厳密な SVC は学習サンプル数に対して O(n^2)〜O(n^3) のため）
	RBF = "rbf"


@dataclass(frozen=True)
class SvmSettings:
	"""svm 固有の設定（CV / 探索の設定は CvSettings）。"""

	kernel: SvmKernel = SvmKernel.LINEAR
	# 入力を fold の学習側で z-score 標準化するか
	standardize: bool = True
	# rbf の Nystroem 近似の次元数（学習サンプル数を超える場合は学習サンプル数に切り詰められる）
	rbf_n_components: int = 1000
	# LinearSVC のソルバの反復上限
	max_iter: int = 10000

	def __post_init__(self) -> None:
		if not isinstance(self.kernel, SvmKernel):
			raise ValueError(f"kernel must be SvmKernel, got {self.kernel!r}")
		if not isinstance(self.standardize, bool):
			raise ValueError(f"standardize must be bool, got {self.standardize!r}")
		if self.rbf_n_components < 1:
			raise ValueError(f"rbf_n_components must be >= 1, got {self.rbf_n_components}")
		if self.max_iter < 1:
			raise ValueError(f"max_iter must be >= 1, got {self.max_iter}")


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
class SvmFoldModel:
	"""1 fold 分の学習済みモデル（学習側で fit した SVM を validation で Platt 較正したもの）。"""

	calibrated: CalibratedClassifierCV

	@property
	def best_iteration(self) -> None:
		return None

	def predict_proba(self, x: np.ndarray) -> np.ndarray:
		"""x: (N, C) → 画像ごとの IN 確率 (N,)"""
		in_col = list(self.calibrated.classes_).index(IN_LABEL)
		return self.calibrated.predict_proba(x)[:, in_col].astype(np.float64)


@dataclass(frozen=True)
class SvmFoldTrainer:
	"""svm の探索空間と 1 fold 分の学習。早期停止は無く、validation は Platt 較正に使う。"""

	settings: SvmSettings

	def params_from_trial(self, trial: optuna.Trial) -> SvmParams:
		return SvmParams.from_trial(trial, self.settings.kernel)

	def train(
		self, params: SvmParams, train: LabeledSamples, val: LabeledSamples, seed: int
	) -> SvmFoldModel:
		scaler = StandardScaler() if self.settings.standardize else "passthrough"
		feature_map: Nystroem | str = "passthrough"
		if params.gamma_factor is not None:
			# gamma の基準値は標準化後（standardize=False では生）の学習側特徴から決める
			scaled = StandardScaler().fit_transform(train.x) if self.settings.standardize else train.x
			feature_map = Nystroem(
				kernel="rbf",
				gamma=params.gamma_factor * scale_gamma(scaled),
				n_components=min(self.settings.rbf_n_components, train.x.shape[0]),
				random_state=seed,
			)
		pipeline = Pipeline([
			("scaler", scaler),
			("feature_map", feature_map),
			("svc", LinearSVC(C=params.c, max_iter=self.settings.max_iter, random_state=seed)),
		])
		pipeline.fit(train.x, train.y)

		# 学習済みの SVM は凍結し、decision_function → IN 確率の sigmoid（Platt）だけを validation で学習する
		calibrated = CalibratedClassifierCV(FrozenEstimator(pipeline), method="sigmoid")
		calibrated.fit(val.x, val.y)
		return SvmFoldModel(calibrated=calibrated)


class SvmMembershipScorer:
	"""
	画像単位の SVM 二値分類（linear: LinearSVC / rbf: Nystroem 近似 + LinearSVC）。
	シャドーペア単位の k-fold CV（fold 内の validation ペアで Platt 較正）の mean - λ·std を
	目的関数として Optuna でハイパーパラメータを探索し、
	最良 trial の k 個の fold モデルの IN 確率の平均でターゲットを推論する。
	"""

	name = "svm"
	score_scale = ScoreScale.PROBABILITY

	def __init__(
		self,
		cv_settings: CvSettings,
		settings: SvmSettings,
		seed: int,
		save_dir: str,
		logger: logging.Logger,
	) -> None:
		self.cv_settings = cv_settings
		self.settings = settings
		self.seed = seed
		self.save_dir = save_dir
		self.logger = logger
		self._best: CvResult[SvmParams, SvmFoldModel] | None = None
		self._diagnostics: dict[str, Any] = {}

	def fit(self, features: ShadowPairFeatures) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。K 枚それぞれを独立した学習サンプルとして展開する。"""
		search = PairCvSearch(
			name=self.name,
			settings=self.cv_settings,
			trainer=SvmFoldTrainer(settings=self.settings),
			seed=self.seed,
			output_dir=os.path.join(self.save_dir, cfg.SVM_CV_DIR),
			logger=self.logger,
			metadata={
				"kernel": self.settings.kernel.value,
				"standardize": self.settings.standardize,
				"rbf_n_components": self.settings.rbf_n_components,
				"max_iter": self.settings.max_iter,
			},
		)
		self._best = None
		outcome = search.run(features)
		self._best = outcome.best
		best_params = outcome.best.params
		self._diagnostics = {
			**outcome.common_diagnostics(self.cv_settings.objective),
			"svm_kernel": self.settings.kernel.value,
			"standardize": self.settings.standardize,
			"best_C": best_params.c,
			# linear のときは未定義（None）
			"best_gamma_factor": best_params.gamma_factor,
			**outcome.trial_state_counts(),
		}

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: K 枚の IN 確率の平均, per_image: (K,) fold モデルのアンサンブル IN 確率"""
		if self._best is None:
			raise RuntimeError("SvmMembershipScorer.fit must be called before score")

		x = np.ascontiguousarray(feats, dtype=np.float32)
		per_image = self._best.predict_proba(x)
		return MembershipScore(value=float(per_image.mean()), per_image=per_image)

	def diagnostics(self) -> dict[str, Any]:
		return dict(self._diagnostics)
