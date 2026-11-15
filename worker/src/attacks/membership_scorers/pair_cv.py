import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar

import numpy as np
import optuna
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import KFold

from src.attacks.mia_attack import MIA_Attack

# 枝刈り: 最初の数 trial は比較対象が無いため枝刈りしない。fold 0 の時点の値でも枝刈りしない
PRUNER_N_STARTUP_TRIALS: int = 5
PRUNER_N_WARMUP_STEPS: int = 1

# TPR@FPR=0.01 を分解できる OUT 画像数の下限（1/0.01）
TPR_AT_1_FPR_TARGET: float = 0.01
TPR_AT_1_FPR_MIN_OUT_IMAGES: int = 100


@dataclass(frozen=True)
class LabeledSamples:
	"""
	学習・評価用に展開した画像単位のサンプル。
	x: (n_groups * K, C), y: (n_groups * K,) IN=1 / OUT=0。
	同じシャドー（グループ）の K 枚は連続して並ぶ。
	images_per_group: シャドー1つの合成画像枚数, = K
	"""

	x: np.ndarray
	y: np.ndarray
	images_per_group: int

	@property
	def num_out_images(self) -> int:
		return int((self.y == 0).sum())

	def group_scores(self, probs: np.ndarray) -> np.ndarray:
		"""画像ごとの IN 確率をシャドーごとに平均する（ターゲットの value と同じ集約）"""
		# 画像方向平均
		return probs.reshape(-1, self.images_per_group).mean(axis=1)	# (2*len(pair_idx)*K, ) -> (2*len(pair_idx), K) -> (2*len(pair_idx),)

	def group_labels(self) -> np.ndarray:
		# [:, 0]: 2次元目の最初の要素のみ取り出す
		# 各シャドーの最初の画像のラベルだけ取り出す
		# そのシャドーの正解ラベルは1個あればいい(全部同じなので)ので代表として最初の1つとってる
		return self.y.reshape(-1, self.images_per_group)[:, 0]	# (2*len(pair_idx)*K, ) -> (2*len(pair_idx), K) -> (2*len(pair_idx),)


@dataclass(frozen=True)
class PairedShadowFeatures:
	"""シャドー IN/OUT ペアの特徴。in_feats, out_feats: (n_pairs, K, C)。分割はペア単位で行う。"""

	in_feats: np.ndarray
	out_feats: np.ndarray

	def __post_init__(self) -> None:
		if self.in_feats.ndim != 3 or self.in_feats.shape != self.out_feats.shape:
			raise ValueError(
				f"in_feats / out_feats must have the same (n_pairs, K, C) shape, "
				f"got {self.in_feats.shape} / {self.out_feats.shape}"
			)

	@property
	def n_pairs(self) -> int:
		return int(self.in_feats.shape[0])

	# 1shadowの合成画像枚数
	@property
	def images_per_shadow(self) -> int:
		return int(self.in_feats.shape[1])

	@property
	def num_classes(self) -> int:
		return int(self.in_feats.shape[2])

	def subset(self, pair_idx: np.ndarray) -> LabeledSamples:
		"""指定ペアの IN シャドー群・OUT シャドー群を画像単位に展開する（IN, OUT の順）"""
		c = self.num_classes
		in_x = self.in_feats[pair_idx].reshape(-1, c)	# (pair, K, C) -> (len(pair_idx), K, C) -> (len(pair_idx)*K, C)
		out_x = self.out_feats[pair_idx].reshape(-1, c)
		x = np.ascontiguousarray(np.concatenate([in_x, out_x]), dtype=np.float32)
		y = np.concatenate([np.ones(in_x.shape[0]), np.zeros(out_x.shape[0])]).astype(np.float32)
		return LabeledSamples(x=x, y=y, images_per_group=self.images_per_shadow)


class CvObjective(str, Enum):
	"""交差検証・早期停止で最大化する汎化性能指標。"""

	# シャドー単位（K 枚の IN 確率平均）の AUC
	AUC = "auc"
	# 画像単位の TPR@FPR=0.01
	TPR_AT_1_FPR = "tpr_at_1_fpr"

	@property
	def min_out_images(self) -> int:
		"""評価集合に必要な OUT 画像数の下限"""
		if self is CvObjective.TPR_AT_1_FPR:
			return TPR_AT_1_FPR_MIN_OUT_IMAGES
		return 1

	# probs: (2*len(pair_idx)*K, )
	# samples: テストデータ
	def evaluate(self, probs: np.ndarray, samples: LabeledSamples) -> float:
		"""probs: 画像ごとの IN 確率 (N,)。評価単位の違いはここに閉じ込める"""
		if self is CvObjective.AUC:
			return float(roc_auc_score(samples.group_labels(), samples.group_scores(probs)))	# ROC-AUCスコア計算
		fpr, tpr, thresholds = roc_curve(samples.y, probs)
		tpr_at, _ = MIA_Attack.get_tpr_and_threshold(fpr, tpr, thresholds, TPR_AT_1_FPR_TARGET)		# FPRか1%の時のTPR計算
		return float(tpr_at)


@dataclass(frozen=True)
class CvSettings:
	"""ペア単位 k-fold CV と Optuna 探索の設定（CV で探索する scorer 共通）。"""

	objective: CvObjective = CvObjective.AUC
	n_folds: int = 10
	# 各 fold の学習側ペアのうち validation（早期停止用）に回す割合
	val_ratio: float = 0.2
	n_trials: int = 50
	# score = mean - stability_lambda * std（未知モデルへの安定性）
	stability_lambda: float = 0.5

	def __post_init__(self) -> None:
		if not isinstance(self.objective, CvObjective):
			raise ValueError(f"objective must be CvObjective, got {self.objective!r}")
		if self.n_folds < 2:
			raise ValueError(f"n_folds must be >= 2, got {self.n_folds}")
		if not 0.0 < self.val_ratio < 1.0:
			raise ValueError(f"val_ratio must be in (0, 1), got {self.val_ratio}")
		if self.n_trials < 1:
			raise ValueError(f"n_trials must be >= 1, got {self.n_trials}")
		if self.stability_lambda < 0:
			raise ValueError(f"stability_lambda must be >= 0, got {self.stability_lambda}")

	def num_val_pairs(self, n_train_pairs: int) -> int:
		"""学習側 n_train_pairs ペアのうち validation に回すペア数（学習・validation とも 1 ペア以上）"""
		return min(max(1, round(n_train_pairs * self.val_ratio)), n_train_pairs - 1)


@dataclass(frozen=True)
class PairSplit:
	"""1 fold のペア index 分割（学習 / validation / テスト）。trial 間で共通にして比較可能にする。"""

	fold: int
	train_idx: np.ndarray
	val_idx: np.ndarray
	test_idx: np.ndarray


# ペア単位の KFold と、各 fold の学習側からの validation 抽出
def make_pair_splits(data: PairedShadowFeatures, settings: CvSettings, seed: int) -> list[PairSplit]:
	if settings.n_folds > data.n_pairs:
		raise ValueError(f"cv_n_folds={settings.n_folds} exceeds n_pairs={data.n_pairs}")
	# 同じペアの IN / OUT は同じ側に入るため、IN/OUT 比はどの集合でも 1:1（層化不要）
	kfold = KFold(n_splits=settings.n_folds, shuffle=True, random_state=seed)
	splits: list[PairSplit] = []
	# ここにおけるindexはpairsのindex
	# np.arrange: 0～n-1までの整数配列作成, 例: 4 -> [0, 1, 2, 3]
	# Kfold.split: 配列を分割
	for fold, (train_val_idx, test_idx) in enumerate(kfold.split(np.arange(data.n_pairs))):
		rng = np.random.RandomState(seed + fold) 	# fold毎にシード変更 validations用シャッフルをfold間で独立に
		shuffled = rng.permutation(train_val_idx)		# permutation: 配列内のエントリをランダムに入れ替える
		n_val = settings.num_val_pairs(len(train_val_idx))	# validationに回す個数取得
		splits.append(PairSplit(
			fold=fold,
			train_idx=np.sort(shuffled[n_val:]),
			val_idx=np.sort(shuffled[:n_val]),
			test_idx=np.sort(test_idx),
		))
	return splits


def validate_pair_splits(
	data: PairedShadowFeatures, splits: list[PairSplit], objective: CvObjective
) -> None:
	"""目的指標が評価集合（テスト fold / validation）で分解可能かを学習前に検証する"""
	required = objective.min_out_images
	min_pairs = min(min(len(s.val_idx), len(s.test_idx)) for s in splits)
	min_out_images = min_pairs * data.images_per_shadow
	if min_out_images < required:
		raise ValueError(
			f"cv_objective={objective.value} requires >= {required} "
			f"OUT images per test fold / validation, got {min_out_images} "
			f"({min_pairs} pairs x K={data.images_per_shadow})"
		)


class TrialParams(Protocol):
	"""1 trial で探索したハイパーパラメータ。"""

	def to_dict(self) -> dict[str, Any]: ...


class FoldModel(Protocol):
	"""1 fold 分の学習済みモデル。"""

	@property
	def best_iteration(self) -> int:
		"""早期停止で採用した反復数（epoch / ブースティングラウンド）"""
		...

	def predict_proba(self, x: np.ndarray) -> np.ndarray:
		"""x: (N, C) → 画像ごとの IN 確率 (N,)"""
		...


P = TypeVar("P", bound=TrialParams)
M = TypeVar("M", bound=FoldModel)


class FoldTrainer(Protocol[P, M]):
	"""探索空間の定義と、1 fold 分の学習（validation による早期停止を含む）を担う。"""

	def params_from_trial(self, trial: optuna.Trial) -> P: ...

	def train(self, params: P, train: LabeledSamples, val: LabeledSamples, seed: int) -> M: ...


@dataclass(frozen=True)
class CvResult(Generic[P, M]):
	"""1 trial 分の交差検証結果。"""

	trial_number: int
	params: P
	fold_scores: list[float]
	fold_models: list[M] = field(repr=False)
	stability_lambda: float

	@property
	def mean(self) -> float:
		return float(np.mean(self.fold_scores))

	@property
	def std(self) -> float:
		# fold 間のばらつき（母標準偏差）
		return float(np.std(self.fold_scores))

	@property
	def score(self) -> float:
		return self.mean - self.stability_lambda * self.std

	@property
	def best_iterations(self) -> list[int]:
		return [m.best_iteration for m in self.fold_models]

	def predict_proba(self, x: np.ndarray) -> np.ndarray:
		"""CV bagging: k 個の fold モデルの画像ごとの IN 確率を平均する"""
		return np.mean([m.predict_proba(x) for m in self.fold_models], axis=0)


@dataclass(frozen=True)
class PairCvOutcome(Generic[P, M]):
	"""探索全体の結果。best は最良 trial、study は全 trial の記録。"""

	best: CvResult[P, M]
	study: optuna.Study

	def common_diagnostics(self, objective: CvObjective) -> dict[str, Any]:
		"""scorer によらない diagnostics"""
		return {
			"cv_objective": objective.value,
			"cv_score": self.best.score,
			"cv_fold_mean": self.best.mean,
			"cv_fold_std": self.best.std,
			"best_trial_number": self.best.trial_number,
		}

	def trial_state_counts(self) -> dict[str, int]:
		states = [t.state for t in self.study.trials]
		return {
			"n_trials_completed": states.count(optuna.trial.TrialState.COMPLETE),
			"n_trials_pruned": states.count(optuna.trial.TrialState.PRUNED),
		}


class PairCvSearch(Generic[P, M]):
	"""
	シャドーペア単位の k-fold CV（fold 内でペア単位の早期停止）の mean - λ·std を目的関数として
	Optuna でハイパーパラメータを探索する。モデル固有の処理は FoldTrainer に委譲する。
	"""

	def __init__(
		self,
		*,
		name: str,
		settings: CvSettings,
		trainer: FoldTrainer[P, M],
		seed: int,
		output_dir: str,
		logger: logging.Logger,
		iteration_label: str,
		metadata: dict[str, Any] | None = None,
	) -> None:
		"""
		name: ログ接頭辞
		iteration_label: folds.json での反復数のキー名（例: best_epoch）
		metadata: best_params.json に追記する scorer 固有の設定
		"""
		self.name = name
		self.settings = settings
		self.trainer = trainer
		self.seed = seed
		self.output_dir = output_dir
		self.logger = logger
		self.iteration_label = iteration_label
		self.metadata = dict(metadata or {})
		self._best: CvResult[P, M] | None = None

	def run(self, in_feats: np.ndarray, out_feats: np.ndarray) -> PairCvOutcome[P, M]:
		"""in_feats, out_feats: (n_pairs, K, C)。K 枚それぞれを独立した学習サンプルとして展開する。"""
		data = PairedShadowFeatures(in_feats=in_feats, out_feats=out_feats)
		splits = make_pair_splits(data, self.settings, self.seed)	# K-fold用にpairを train/validation/testに分割
		validate_pair_splits(data, splits, self.settings.objective)

		self._best = None
		optuna.logging.set_verbosity(optuna.logging.WARNING)
		study = optuna.create_study(
			direction="maximize",
			sampler=optuna.samplers.TPESampler(seed=self.seed),	# 探し方
			pruner=optuna.pruners.MedianPruner(					# 枝狩り これまで終了したtrialの中央値より悪ければその探索、trialは打ち切り
				# 最初のPRUNER_N_STARTUP_TRIALS回のtrialは打ち切らない、trial内でPRUNER_N_WARMUP_STEPSステップは打ち切らない
				n_startup_trials=PRUNER_N_STARTUP_TRIALS, n_warmup_steps=PRUNER_N_WARMUP_STEPS
			),
		)
		# trialを変化させて _run_trialの戻り値で評価、探索
		study.optimize(
			lambda trial: self._run_trial(trial, data, splits), n_trials=self.settings.n_trials	# n_trials: 最大探索回数
		)
		if self._best is None:
			raise RuntimeError(f"{self.name}: no trial completed")

		self._save_outputs(study, splits, self._best)
		return PairCvOutcome(best=self._best, study=study)

	# 試行をしてスコアを返す
	def _run_trial(
		self, trial: optuna.Trial, data: PairedShadowFeatures, splits: list[PairSplit]
	) -> float:
		params = self.trainer.params_from_trial(trial)	# optunaのサンプラーによってパラメータ決定
		fold_scores: list[float] = []
		fold_models: list[M] = []
		# K-fold
		for split in splits:
			# 学習
			fold_model = self.trainer.train(
				params,
				data.subset(split.train_idx),
				data.subset(split.val_idx),
				seed=self.seed + trial.number * self.settings.n_folds + split.fold,	# 全てのtrailの全てのfoldで独立になるように
			)
			# 汎化性能評価
			test = data.subset(split.test_idx)
			fold_scores.append(self.settings.objective.evaluate(fold_model.predict_proba(test.x), test))
			fold_models.append(fold_model)

			# trial途中打ち切り
			trial.report(float(np.mean(fold_scores)), step=split.fold)	# 評価平均値報告
			if trial.should_prune():
				self.logger.info(
					f"{self.name} trial {trial.number} pruned at fold {split.fold} "
					f"(partial mean={np.mean(fold_scores):.4f})"
				)
				raise optuna.TrialPruned()

		result = CvResult(
			trial_number=trial.number,
			params=params,
			fold_scores=fold_scores,
			fold_models=fold_models,
			stability_lambda=self.settings.stability_lambda,
		)
		trial.set_user_attr("fold_scores", fold_scores)
		trial.set_user_attr(f"{self.iteration_label}s", result.best_iterations)
		trial.set_user_attr("cv_mean", result.mean)
		trial.set_user_attr("cv_std", result.std)
		# 全 trial の fold モデルを保持するとメモリを食うため、最良値を更新した trial のみ保持する
		if self._best is None or result.score > self._best.score:
			self._best = result
		self.logger.info(
			f"{self.name} trial {trial.number}: score={result.score:.4f} "
			f"(mean={result.mean:.4f}, std={result.std:.4f}) params={params.to_dict()}"
		)
		return result.score

	def _save_outputs(
		self, study: optuna.Study, splits: list[PairSplit], best: CvResult[P, M]
	) -> None:
		os.makedirs(self.output_dir, exist_ok=True)

		study.trials_dataframe().to_csv(os.path.join(self.output_dir, "trials.csv"), index=False)
		with open(os.path.join(self.output_dir, "best_params.json"), "w") as f:
			json.dump({
				"trial_number": best.trial_number,
				"objective": self.settings.objective.value,
				"stability_lambda": self.settings.stability_lambda,
				**self.metadata,
				"cv_score": best.score,
				"cv_mean": best.mean,
				"cv_std": best.std,
				**best.params.to_dict(),
			}, f, indent=2)
		with open(os.path.join(self.output_dir, "folds.json"), "w") as f:
			json.dump([
				{
					"fold": split.fold,
					"score": score,
					self.iteration_label: model.best_iteration,
					"train_pairs": split.train_idx.tolist(),
					"val_pairs": split.val_idx.tolist(),
					"test_pairs": split.test_idx.tolist(),
				}
				for split, score, model in zip(
					splits, best.fold_scores, best.fold_models, strict=True
				)
			], f, indent=2)
		self.logger.info(f"{self.name} CV results saved -> {self.output_dir}")
