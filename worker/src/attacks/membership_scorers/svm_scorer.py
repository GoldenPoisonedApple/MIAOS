import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import optuna
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

import src.core.config as cfg
from src.attacks.membership_scorers.base import (
	DecisionAnalysisData,
	MembershipScore,
	ScoreScale,
	ShadowPairFeatures,
)
from src.attacks.membership_scorers.pair_cv import (
	CvResult,
	CvSettings,
	LabeledSamples,
	PairCvSearch,
	SampleLayout,
)
from src.attacks.membership_scorers.rbf_nystroem import RbfNystroem
from src.attacks.membership_scorers.svm_common import (
	C_RANGE,
	GAMMA_FACTOR_RANGE,
	OofLogits,
	SvmFoldModel,
	SvmKernel,
	SvmParams,
	build_decision_analysis,
	calibrate_fold,
	oof_logits,
	scale_gamma,
)

__all__ = [
	"C_RANGE",
	"GAMMA_FACTOR_RANGE",
	"SvmFoldModel",
	"SvmFoldTrainer",
	"SvmKernel",
	"SvmMembershipScorer",
	"SvmParams",
	"SvmSettings",
	"scale_gamma",
]


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
class SvmFoldTrainer:
	"""svm の探索空間と 1 fold 分の学習。早期停止は無く、validation は Platt 較正に使う。"""

	settings: SvmSettings

	def params_from_trial(self, trial: optuna.Trial) -> SvmParams:
		return SvmParams.from_trial(trial, self.settings.kernel)

	def train(
		self, params: SvmParams, train: LabeledSamples, val: LabeledSamples, seed: int
	) -> SvmFoldModel:
		scaler = StandardScaler() if self.settings.standardize else "passthrough"
		feature_map: RbfNystroem | str = "passthrough"
		if params.gamma_factor is not None:
			# gamma の基準値は標準化後（standardize=False では生）の学習側特徴から決める
			scaled = StandardScaler().fit_transform(train.x) if self.settings.standardize else train.x
			feature_map = RbfNystroem(
				gamma=params.gamma_factor * scale_gamma(scaled),
				n_components=min(self.settings.rbf_n_components, train.x.shape[0]),
				random_state=seed,
			)
		pipeline = Pipeline([
			("scaler", scaler),
			("feature_map", feature_map),
			("svc", LinearSVC(C=params.c, max_iter=self.settings.max_iter, random_state=seed)),
		])
		# 学習済みの SVM は固定し、decision_function → IN 確率の sigmoid（Platt）だけを validation で学習する
		return calibrate_fold(pipeline, train, val)


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
		# 可視化用のシャドーの out-of-fold logit（画像単位）
		self._oof: OofLogits | None = None
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
			layout=SampleLayout.PER_IMAGE,
		)
		self._best = None
		self._oof = None
		outcome = search.run(features)
		self._best = outcome.best
		self._oof = oof_logits(outcome, features)
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

	def decision_analysis(
		self, target_feats: np.ndarray, target_fractions: np.ndarray
	) -> DecisionAnalysisData:
		"""target_feats: (T, K, C), target_fractions: (T,) → 画像単位の可視化データ"""
		if self._best is None or self._oof is None:
			raise RuntimeError("SvmMembershipScorer.fit must be called before decision_analysis")
		return build_decision_analysis(
			self.name, SampleLayout.PER_IMAGE, self._oof, self._best, target_feats, target_fractions
		)

	def diagnostics(self) -> dict[str, Any]:
		return dict(self._diagnostics)
