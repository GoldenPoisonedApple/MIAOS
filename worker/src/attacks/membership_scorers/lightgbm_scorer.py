import logging
import os
from dataclasses import dataclass
from typing import Any

import lightgbm as lgb
import numpy as np
import optuna
from sklearn.metrics import log_loss

import src.core.config as cfg
from src.attacks.membership_scorers.base import MembershipScore, ScoreScale, ShadowPairFeatures
from src.attacks.membership_scorers.pair_cv import (
	CvObjective,
	CvResult,
	CvSettings,
	LabeledSamples,
	PairCvSearch,
)

# 探索空間（固定）
LEARNING_RATE_RANGE: tuple[float, float] = (1e-3, 0.3)
NUM_LEAVES_RANGE: tuple[int, int] = (4, 64)
MAX_DEPTH_RANGE: tuple[int, int] = (3, 8)
MIN_CHILD_SAMPLES_RANGE: tuple[int, int] = (5, 100)
FEATURE_FRACTION_RANGE: tuple[float, float] = (0.3, 1.0)
BAGGING_FRACTION_RANGE: tuple[float, float] = (0.5, 1.0)
LAMBDA_RANGE: tuple[float, float] = (1e-8, 10.0)
# bagging_fraction が正則化の強さを決め、頻度は効果が小さいため毎ラウンド再抽出に固定
BAGGING_FREQ: int = 1
# LightGBM の max_depth で深さ無制限を表す値
UNLIMITED_DEPTH: int = -1

VAL_DATASET_NAME = "val"
LOGLOSS_METRIC_NAME = "logloss"


@dataclass(frozen=True)
class LightGbmSettings:
	"""lightgbm 固有の早期停止の設定（CV / 探索の設定は CvSettings）。"""

	# validation の目的指標が改善しないまま許容するブースティングラウンド数
	patience: int = 50
	# ブースティングラウンドの上限（実際の木の本数は早期停止で決まる）
	max_rounds: int = 1000

	def __post_init__(self) -> None:
		if self.patience < 1:
			raise ValueError(f"patience must be >= 1, got {self.patience}")
		if self.max_rounds < 1:
			raise ValueError(f"max_rounds must be >= 1, got {self.max_rounds}")


@dataclass(frozen=True)
class LightGbmParams:
	"""1 trial で探索するハイパーパラメータ。max_depth=UNLIMITED_DEPTH は深さ無制限。"""

	learning_rate: float
	num_leaves: int
	max_depth: int
	min_child_samples: int
	feature_fraction: float
	bagging_fraction: float
	lambda_l1: float
	lambda_l2: float

	@classmethod
	def from_trial(cls, trial: optuna.Trial) -> "LightGbmParams":
		learning_rate = trial.suggest_float("learning_rate", *LEARNING_RATE_RANGE, log=True)
		num_leaves = trial.suggest_int("num_leaves", *NUM_LEAVES_RANGE, log=True)
		# 深さの上限は制限するときだけ意味を持つ（条件付き探索）
		limit_depth = trial.suggest_categorical("limit_depth", [False, True])
		max_depth = (
			trial.suggest_int("max_depth", *MAX_DEPTH_RANGE) if limit_depth else UNLIMITED_DEPTH
		)
		return cls(
			learning_rate=learning_rate,
			num_leaves=num_leaves,
			max_depth=max_depth,
			min_child_samples=trial.suggest_int("min_child_samples", *MIN_CHILD_SAMPLES_RANGE, log=True),
			feature_fraction=trial.suggest_float("feature_fraction", *FEATURE_FRACTION_RANGE),
			bagging_fraction=trial.suggest_float("bagging_fraction", *BAGGING_FRACTION_RANGE),
			lambda_l1=trial.suggest_float("lambda_l1", *LAMBDA_RANGE, log=True),
			lambda_l2=trial.suggest_float("lambda_l2", *LAMBDA_RANGE, log=True),
		)

	def to_dict(self) -> dict[str, Any]:
		return {
			"learning_rate": self.learning_rate,
			"num_leaves": self.num_leaves,
			"max_depth": self.max_depth,
			"min_child_samples": self.min_child_samples,
			"feature_fraction": self.feature_fraction,
			"bagging_fraction": self.bagging_fraction,
			"lambda_l1": self.lambda_l1,
			"lambda_l2": self.lambda_l2,
		}

	def to_lgb_params(self, seed: int) -> dict[str, Any]:
		return {
			"objective": "binary",
			# 組み込み指標は使わず、feval の目的指標と logloss のみで評価する
			"metric": "None",
			**self.to_dict(),
			"bagging_freq": BAGGING_FREQ,
			"seed": seed,
			# 同じ seed で結果を再現させる（col-wise を固定しないと探索方式の自動選択で結果が揺れる）
			"deterministic": True,
			"force_col_wise": True,
			"verbosity": -1,
		}


class LexicographicEarlyStopping:
	"""
	validation の目的指標を主、logloss を副（小さいほど良い）とした辞書式比較で best を追跡し、
	patience ラウンド改善しなければ学習を打ち切る（neural_regularized の早期停止と同じ基準）。
	組み込みの early_stopping は指標を 1 つずつしか比較できないため自前で実装する。
	"""

	# 組み込みの early_stopping と同じ実行順
	order = 30

	def __init__(self, objective: CvObjective, patience: int) -> None:
		self.objective = objective
		self.patience = patience
		self.best_key: tuple[float, float] | None = None
		# 採用するラウンド数（1 始まり）
		self.best_iteration = 0
		self._best_results: list[Any] = []

	def __call__(self, env: lgb.callback.CallbackEnv) -> None:
		results = {r[1]: r[2] for r in env.evaluation_result_list or [] if r[0] == VAL_DATASET_NAME}
		key = (results[self.objective.value], -results[LOGLOSS_METRIC_NAME])
		if self.best_key is None or key > self.best_key:
			self.best_key = key
			self.best_iteration = env.iteration + 1
			self._best_results = list(env.evaluation_result_list or [])
		elif env.iteration + 1 - self.best_iteration >= self.patience:
			# EarlyStopException は 0 始まりの反復番号を受け取る
			raise lgb.callback.EarlyStopException(self.best_iteration - 1, self._best_results)


@dataclass(frozen=True)
class LightGbmFoldModel:
	"""1 fold 分の学習済みモデル。推論には早期停止で採用したラウンドまでの木を使う。"""

	booster: lgb.Booster
	best_iteration: int

	def predict_proba(self, x: np.ndarray) -> np.ndarray:
		"""x: (N, C) → 画像ごとの IN 確率 (N,)"""
		probs = self.booster.predict(x, num_iteration=self.best_iteration)
		return np.asarray(probs, dtype=np.float64)


@dataclass(frozen=True)
class LightGbmFoldTrainer:
	"""lightgbm の探索空間と 1 fold 分の学習。"""

	settings: LightGbmSettings
	objective: CvObjective

	def params_from_trial(self, trial: optuna.Trial) -> LightGbmParams:
		return LightGbmParams.from_trial(trial)

	def train(
		self, params: LightGbmParams, train: LabeledSamples, val: LabeledSamples, seed: int
	) -> LightGbmFoldModel:
		train_set = lgb.Dataset(train.x, label=train.y)
		val_set = lgb.Dataset(val.x, label=val.y, reference=train_set)

		# 組み込みの binary 目的関数では preds は sigmoid 後の IN 確率
		def feval(preds: np.ndarray, _: lgb.Dataset) -> list[tuple[str, float, bool]]:
			probs = np.asarray(preds, dtype=np.float64)
			return [
				(self.objective.value, self.objective.evaluate(probs, val), True),	# CVスコア
				(LOGLOSS_METRIC_NAME, float(log_loss(val.y, probs, labels=[0, 1])), False),	# Loss
			]

		early_stopping = LexicographicEarlyStopping(self.objective, self.settings.patience)
		booster = lgb.train(
			params.to_lgb_params(seed),
			train_set,
			num_boost_round=self.settings.max_rounds,
			valid_sets=[val_set],
			valid_names=[VAL_DATASET_NAME],
			feval=feval,
			callbacks=[early_stopping],
		)
		return LightGbmFoldModel(booster=booster, best_iteration=early_stopping.best_iteration)


class LightGbmMembershipScorer:
	"""
	画像単位の LightGBM 二値分類。シャドーペア単位の k-fold CV（fold 内でペア単位の早期停止）の
	mean - λ·std を目的関数として Optuna でハイパーパラメータを探索し、
	最良 trial の k 個の fold モデルの IN 確率の平均でターゲットを推論する。
	木モデルは特徴の単調変換で分割が変わらないため標準化しない。
	"""

	name = "lightgbm"
	score_scale = ScoreScale.PROBABILITY

	def __init__(
		self,
		cv_settings: CvSettings,
		settings: LightGbmSettings,
		seed: int,
		save_dir: str,
		logger: logging.Logger,
	) -> None:
		self.cv_settings = cv_settings
		self.settings = settings
		self.seed = seed
		self.save_dir = save_dir
		self.logger = logger
		self._best: CvResult[LightGbmParams, LightGbmFoldModel] | None = None
		self._diagnostics: dict[str, Any] = {}

	def fit(self, features: ShadowPairFeatures) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。K 枚それぞれを独立した学習サンプルとして展開する。"""
		search = PairCvSearch(
			name=self.name,
			settings=self.cv_settings,
			trainer=LightGbmFoldTrainer(settings=self.settings, objective=self.cv_settings.objective),
			seed=self.seed,
			output_dir=os.path.join(self.save_dir, cfg.LIGHTGBM_CV_DIR),
			logger=self.logger,
			iteration_label="best_iteration",
			metadata={"patience": self.settings.patience, "max_rounds": self.settings.max_rounds},
		)
		self._best = None
		outcome = search.run(features)
		self._best = outcome.best
		self._diagnostics = {
			**outcome.common_diagnostics(self.cv_settings.objective),
			**{f"best_{k}": v for k, v in outcome.best.params.to_dict().items()},
			"best_iteration_median": float(np.median(outcome.best.best_iterations)),
			**outcome.trial_state_counts(),
		}

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: K 枚の IN 確率の平均, per_image: (K,) fold モデルのアンサンブル IN 確率"""
		if self._best is None:
			raise RuntimeError("LightGbmMembershipScorer.fit must be called before score")

		x = np.ascontiguousarray(feats, dtype=np.float32)
		per_image = self._best.predict_proba(x)
		return MembershipScore(value=float(per_image.mean()), per_image=per_image)

	def diagnostics(self) -> dict[str, Any]:
		return dict(self._diagnostics)
