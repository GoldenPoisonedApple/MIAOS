import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import optuna
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

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
from src.attacks.membership_scorers.svm_common import (
	OofLogits,
	SvmFoldModel,
	SvmKernel,
	SvmParams,
	build_decision_analysis,
	calibrate_fold,
	oof_logits,
	scale_gamma,
)

LAYOUT = SampleLayout.FLAT


@dataclass(frozen=True)
class FlatSvmSettings:
	"""flat_svm 固有の設定（CV / 探索の設定は CvSettings）。"""

	kernel: SvmKernel = SvmKernel.LINEAR
	# 入力を fold の学習側で z-score 標準化するか
	standardize: bool = True

	def __post_init__(self) -> None:
		if not isinstance(self.kernel, SvmKernel):
			raise ValueError(f"kernel must be SvmKernel, got {self.kernel!r}")
		if not isinstance(self.standardize, bool):
			raise ValueError(f"standardize must be bool, got {self.standardize!r}")


@dataclass(frozen=True)
class FlatSvmFoldTrainer:
	"""flat_svm の探索空間と 1 fold 分の学習。早期停止は無く、validation は Platt 較正に使う。"""

	settings: FlatSvmSettings

	def params_from_trial(self, trial: optuna.Trial) -> SvmParams:
		return SvmParams.from_trial(trial, self.settings.kernel)

	def train(
		self, params: SvmParams, train: LabeledSamples, val: LabeledSamples, seed: int
	) -> SvmFoldModel:
		scaler = StandardScaler() if self.settings.standardize else "passthrough"
		if params.gamma_factor is None:
			svc = SVC(kernel="linear", C=params.c)
		else:
			# gamma の基準値は標準化後（standardize=False では生）の学習側特徴から決める
			scaled = StandardScaler().fit_transform(train.x) if self.settings.standardize else train.x
			svc = SVC(kernel="rbf", C=params.c, gamma=params.gamma_factor * scale_gamma(scaled))
		# SVC は probability=False では乱数を使わないため seed は不要
		pipeline = Pipeline([("scaler", scaler), ("svc", svc)])
		return calibrate_fold(pipeline, train, val)


class FlatSvmMembershipScorer:
	"""
	シャドー単位の SVM 二値分類（linear: SVC(kernel="linear") / rbf: SVC(kernel="rbf")）。
	シャドーの特徴 (K, C) を (K*C) に平坦化して 1 サンプルとし（サンプル数は n_pairs * 2）、
	シャドーペア単位の k-fold CV（fold 内の validation ペアで Platt 較正）の mean - λ·std を
	目的関数として Optuna でハイパーパラメータを探索し、
	最良 trial の k 個の fold モデルの IN 確率の平均でターゲットを推論する。
	"""

	name = "flat_svm"
	score_scale = ScoreScale.PROBABILITY

	def __init__(
		self,
		cv_settings: CvSettings,
		settings: FlatSvmSettings,
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
		# 可視化用のシャドーの out-of-fold logit（シャドー単位）
		self._oof: OofLogits | None = None
		self._diagnostics: dict[str, Any] = {}

	def fit(self, features: ShadowPairFeatures) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。シャドーごとに (K*C) に平坦化して 1 サンプルとする。"""
		search = PairCvSearch(
			name=self.name,
			settings=self.cv_settings,
			trainer=FlatSvmFoldTrainer(settings=self.settings),
			seed=self.seed,
			output_dir=os.path.join(self.save_dir, cfg.FLAT_SVM_CV_DIR),
			logger=self.logger,
			metadata={
				"kernel": self.settings.kernel.value,
				"standardize": self.settings.standardize,
			},
			layout=LAYOUT,
		)
		self._best = None
		self._oof = None
		outcome = search.run(features)
		self._best = outcome.best
		self._oof = oof_logits(outcome, features)
		best_params = outcome.best.params
		self._diagnostics = {
			**outcome.common_diagnostics(self.cv_settings.objective),
			"flat_svm_kernel": self.settings.kernel.value,
			"standardize": self.settings.standardize,
			"best_C": best_params.c,
			# linear のときは未定義（None）
			"best_gamma_factor": best_params.gamma_factor,
			**outcome.trial_state_counts(),
		}

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""
		feats: (K, C) → value: fold モデルのアンサンブル IN 確率,
		per_image: (K,) value を K 個並べたもの（モデルは K 枚を結合して判定するため画像単位に分解しない）
		"""
		if self._best is None:
			raise RuntimeError("FlatSvmMembershipScorer.fit must be called before score")

		x = np.ascontiguousarray(LAYOUT.flatten_target(np.asarray(feats)), dtype=np.float32)	# (K, C) -> (1, K*C)
		value = float(self._best.predict_proba(x)[0])
		return MembershipScore(value=value, per_image=np.full(feats.shape[0], value))

	def decision_analysis(
		self, target_feats: np.ndarray, target_fractions: np.ndarray
	) -> DecisionAnalysisData:
		"""target_feats: (T, K, C), target_fractions: (T,) → シャドー単位の可視化データ"""
		if self._best is None or self._oof is None:
			raise RuntimeError("FlatSvmMembershipScorer.fit must be called before decision_analysis")
		return build_decision_analysis(
			self.name, LAYOUT, self._oof, self._best, target_feats, target_fractions
		)

	def diagnostics(self) -> dict[str, Any]:
		return dict(self._diagnostics)
