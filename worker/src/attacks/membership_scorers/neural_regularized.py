import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import optuna
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import KFold

import src.core.config as cfg
from src.attacks.membership_scorers.base import MembershipScore, ScoreScale
from src.attacks.mia_attack import MIA_Attack
from src.models.attack_model import BinaryAttackNet

# 探索空間（固定）
LR_RANGE: tuple[float, float] = (1e-5, 1e-3)
WEIGHT_DECAY_RANGE: tuple[float, float] = (1e-5, 1e-1)
HIDDEN_DIM_RANGE: tuple[int, int] = (8, 128)
DROPOUT_RANGE: tuple[float, float] = (0.0, 0.5)

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
class NeuralRegularizedSettings:
	"""neural_regularized の CV / 探索 / 早期停止の設定。"""

	objective: CvObjective = CvObjective.AUC
	n_folds: int = 10
	# 各 fold の学習側ペアのうち validation（早期停止用）に回す割合
	val_ratio: float = 0.2
	n_trials: int = 50
	# score = mean - stability_lambda * std（未知モデルへの安定性）
	stability_lambda: float = 0.5
	patience: int = 20
	max_epochs: int = 500
	batch_size: int = cfg.ATTACK_MODEL_BATCH_SIZE
	# 入力を fold の学習側で z-score 標準化するか（False では恒等変換）
	standardize: bool = True

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
		if self.patience < 1:
			raise ValueError(f"patience must be >= 1, got {self.patience}")
		if self.max_epochs < 1:
			raise ValueError(f"max_epochs must be >= 1, got {self.max_epochs}")
		if self.batch_size < 1:
			raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")
		if not isinstance(self.standardize, bool):
			raise ValueError(f"standardize must be bool, got {self.standardize!r}")

	def num_val_pairs(self, n_train_pairs: int) -> int:
		"""学習側 n_train_pairs ペアのうち validation に回すペア数（学習・validation とも 1 ペア以上）"""
		return min(max(1, round(n_train_pairs * self.val_ratio)), n_train_pairs - 1)


@dataclass(frozen=True)
class ArchitectureParams:
	"""1 trial で探索するハイパーパラメータ。hidden_dim=None は隠れ層 0 層。"""

	lr: float
	weight_decay: float
	hidden_dim: int | None
	dropout: float

	@classmethod
	def from_trial(cls, trial: optuna.Trial) -> "ArchitectureParams":
		lr = trial.suggest_float("lr", *LR_RANGE, log=True)
		weight_decay = trial.suggest_float("weight_decay", *WEIGHT_DECAY_RANGE, log=True)
		n_hidden = trial.suggest_int("n_hidden", 0, 1)
		# 隠れ層の幅と dropout は隠れ層があるときだけ意味を持つ（条件付き探索）
		if n_hidden == 0:
			return cls(lr=lr, weight_decay=weight_decay, hidden_dim=None, dropout=0.0)
		hidden_dim = trial.suggest_int("hidden_dim", *HIDDEN_DIM_RANGE, log=True)
		dropout = trial.suggest_float("dropout", *DROPOUT_RANGE)
		return cls(lr=lr, weight_decay=weight_decay, hidden_dim=hidden_dim, dropout=dropout)

	def to_dict(self) -> dict[str, Any]:
		return {
			"lr": self.lr,
			"weight_decay": self.weight_decay,
			"n_hidden": 0 if self.hidden_dim is None else 1,
			"hidden_dim": self.hidden_dim,
			"dropout": self.dropout,
		}


@dataclass(frozen=True)
class FeatureStandardizer:
	"""学習側で fit した z-score 標準化。分散 0 の次元は分母を 1 とする。"""

	mean: np.ndarray
	std: np.ndarray

	# x: (2*len(pair_idx)*K, C) 最初の次元方向へのz-score
	@classmethod
	def fit(cls, x: np.ndarray) -> "FeatureStandardizer":
		mean = x.mean(axis=0)
		std = x.std(axis=0)
		std = np.where(std > 0, std, 1.0)
		return cls(mean=mean.astype(np.float32), std=std.astype(np.float32))

	# 標準化しない場合の恒等変換（mean=0, std=1）。FoldModel と推論の経路を共通にするため
	@classmethod
	def identity(cls, num_features: int) -> "FeatureStandardizer":
		return cls(
			mean=np.zeros(num_features, dtype=np.float32),
			std=np.ones(num_features, dtype=np.float32),
		)

	# 計算したmeanとstdを使ってxを標準化
	def transform(self, x: np.ndarray) -> np.ndarray:
		return ((x - self.mean) / self.std).astype(np.float32)


@dataclass(frozen=True)
class FoldModel:
	"""1 fold 分の学習済みモデル（自分の標準化パラメータを持つ）。"""

	standardizer: FeatureStandardizer
	model: BinaryAttackNet
	best_epoch: int

	def predict_proba(self, x: np.ndarray) -> np.ndarray:
		"""x: (N, C) → 画像ごとの IN 確率 (N,)"""
		x_t = torch.from_numpy(self.standardizer.transform(x)).to(cfg.DEVICE)
		self.model.eval()
		with torch.no_grad():
			probs = torch.sigmoid(self.model(x_t))
		return probs.cpu().numpy().astype(np.float64)


def train_with_early_stopping(
	params: ArchitectureParams,
	train: LabeledSamples,
	val: LabeledSamples,
	settings: NeuralRegularizedSettings,
	seed: int,
) -> FoldModel:
	"""
	BCEWithLogitsLoss で学習し、validation 上の目的指標（同値時は validation BCE が小さい方）で
	早期停止する。停止後は best の重みを復元する。
	スケジューラは使わない（epoch 数が不定のため CosineAnnealing の T_max を決められない）。
	"""
	torch.manual_seed(seed)
	generator = torch.Generator().manual_seed(seed)

	# z-score 標準化（standardize=False では恒等変換）
	standardizer = (
		FeatureStandardizer.fit(train.x)
		if settings.standardize
		else FeatureStandardizer.identity(train.x.shape[1])
	)

	train_x = torch.from_numpy(standardizer.transform(train.x)).to(cfg.DEVICE)
	train_y = torch.from_numpy(train.y).to(cfg.DEVICE)
	val_x = torch.from_numpy(standardizer.transform(val.x)).to(cfg.DEVICE)
	val_y = torch.from_numpy(val.y).to(cfg.DEVICE)

	# モデル作成
	model = BinaryAttackNet(
		input_dim=train.x.shape[1], hidden_dim=params.hidden_dim, dropout=params.dropout
	).to(cfg.DEVICE)
	criterion = nn.BCEWithLogitsLoss() # 損失関数 内部でシグモイド関数通したあとBCE(Binary Cross Entropy)計算する関数
	optimizer = torch.optim.AdamW(model.parameters(), lr=params.lr, weight_decay=params.weight_decay)	# モデルパラメータの参照, 学習設定

	n_train = train_x.shape[0] # 学習データ数: (2*len(pair_idx)*K, C) -> 2*len(pair_idx)*K
	best_key: tuple[float, float] | None = None
	best_state: dict[str, torch.Tensor] = {}
	best_epoch = 0
	epochs_without_improvement = 0
	# 学習
	for epoch in range(settings.max_epochs):
		# 学習
		model.train()	# 学習モード
		# データが小さいため DataLoader を使わず、デバイス上でシャッフルしてミニバッチを切り出す、学習のデータ順をシャッフルする
		perm = torch.randperm(n_train, generator=generator).to(cfg.DEVICE)	# randperm: 0～n_train-1までの整数をランダムに並べた配列作成
		for start in range(0, n_train, settings.batch_size): 	# range(start, end, step)
			batch = perm[start:start + settings.batch_size]		# batch_size分だけ使うデータのインデックスをとる
			optimizer.zero_grad()	# 前回の勾配を消す
			loss = criterion(model(train_x[batch]), train_y[batch]) # forwardの結果とラベルから損失計算
			loss.backward()			# 損失から勾配計算
			optimizer.step()		# 勾配から重み更新

		# この学習の評価
		model.eval()	# 評価モード
		with torch.no_grad():
			val_logits = model(val_x)
			val_loss = float(criterion(val_logits, val_y).item())	# 枚数分から平均した損失
			val_probs = torch.sigmoid(val_logits).cpu().numpy().astype(np.float64)
   
		# スコア計算
		val_metric = settings.objective.evaluate(val_probs, val)
  
		# 目的指標を主、validation BCE を副（小さいほど良いので符号反転）とした辞書式比較
		key = (val_metric, -val_loss)	# 1つ目が同じ場合は2つ目で比較
		if best_key is None or key > best_key:
			best_key = key
			best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
			best_epoch = epoch + 1
			epochs_without_improvement = 0
		else:
			epochs_without_improvement += 1
			# early stopping
			if epochs_without_improvement >= settings.patience:
				break

	# 最もよかったモデルを出力
	model.load_state_dict(best_state)
	model.eval()
	return FoldModel(standardizer=standardizer, model=model, best_epoch=best_epoch)


@dataclass(frozen=True)
class PairSplit:
	"""1 fold のペア index 分割（学習 / validation / テスト）。trial 間で共通にして比較可能にする。"""

	fold: int
	train_idx: np.ndarray
	val_idx: np.ndarray
	test_idx: np.ndarray


@dataclass(frozen=True)
class CvResult:
	"""1 trial 分の交差検証結果。"""

	trial_number: int
	params: ArchitectureParams
	fold_scores: list[float]
	fold_models: list[FoldModel] = field(repr=False)
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
	def best_epochs(self) -> list[int]:
		return [m.best_epoch for m in self.fold_models]


class NeuralRegularizedMembershipScorer:
	"""
	過学習対策をした 1 出力 MLP。シャドーペア単位の k-fold CV（fold 内でペア単位の早期停止）の
	mean - λ·std を目的関数として Optuna でハイパーパラメータを探索し、
	最良 trial の k 個の fold モデルの IN 確率の平均でターゲットを推論する。
	"""

	name = "neural_regularized"
	score_scale = ScoreScale.PROBABILITY

	def __init__(
		self,
		settings: NeuralRegularizedSettings,
		seed: int,
		save_dir: str,
		logger: logging.Logger,
	) -> None:
		self.settings = settings
		self.seed = seed
		self.save_dir = save_dir
		self.logger = logger
		self._best: CvResult | None = None
		self._diagnostics: dict[str, Any] = {}

	def fit(self, in_feats: np.ndarray, out_feats: np.ndarray) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。K 枚それぞれを独立した学習サンプルとして展開する。"""
		data = PairedShadowFeatures(in_feats=in_feats, out_feats=out_feats)
		splits = self._make_splits(data)	# K-fold用にpairを train/validation/testに分割
		self._validate_splits(data, splits)

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
			raise RuntimeError("neural_regularized: no trial completed")

		self._save_outputs(study, splits)
		self._diagnostics = self._build_diagnostics(study)

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: K 枚の IN 確率の平均, per_image: (K,) fold モデルのアンサンブル IN 確率"""
		if self._best is None:
			raise RuntimeError("NeuralRegularizedMembershipScorer.fit must be called before score")

		x = np.ascontiguousarray(feats, dtype=np.float32)	# float32に変換、メモリ上の連続した位置に配置
		# CV bagging: 最もスコアが良かったtrialのk-foldの複数のモデルをそのままアンサンブルして推論に使用
		per_image = np.mean([m.predict_proba(x) for m in self._best.fold_models], axis=0)
		# スコアは平均とする
		return MembershipScore(value=float(per_image.mean()), per_image=per_image)

	def diagnostics(self) -> dict[str, Any]:
		return dict(self._diagnostics)

	# ペア単位の KFold と、各 fold の学習側からの validation 抽出
	def _make_splits(self, data: PairedShadowFeatures) -> list[PairSplit]:
		if self.settings.n_folds > data.n_pairs:
			raise ValueError(
				f"neural_regularized_n_folds={self.settings.n_folds} exceeds n_pairs={data.n_pairs}"
			)
		# 同じペアの IN / OUT は同じ側に入るため、IN/OUT 比はどの集合でも 1:1（層化不要）
		kfold = KFold(n_splits=self.settings.n_folds, shuffle=True, random_state=self.seed)
		splits: list[PairSplit] = []
		# ここにおけるindexはpairsのindex
		# np.arrange: 0～n-1までの整数配列作成, 例: 4 -> [0, 1, 2, 3]
		# Kfold.split: 配列を分割
		for fold, (train_val_idx, test_idx) in enumerate(kfold.split(np.arange(data.n_pairs))):
			rng = np.random.RandomState(self.seed + fold) 	# fold毎にシード変更 validations用シャッフルをfold間で独立に
			shuffled = rng.permutation(train_val_idx)		# permutation: 配列内のエントリをランダムに入れ替える
			n_val = self.settings.num_val_pairs(len(train_val_idx))	# validationに回す個数取得
			splits.append(PairSplit(
				fold=fold,
				train_idx=np.sort(shuffled[n_val:]),
				val_idx=np.sort(shuffled[:n_val]),
				test_idx=np.sort(test_idx),
			))
		return splits

	def _validate_splits(self, data: PairedShadowFeatures, splits: list[PairSplit]) -> None:
		"""目的指標が評価集合（テスト fold / validation）で分解可能かを学習前に検証する"""
		required = self.settings.objective.min_out_images
		min_pairs = min(min(len(s.val_idx), len(s.test_idx)) for s in splits)
		min_out_images = min_pairs * data.images_per_shadow
		if min_out_images < required:
			raise ValueError(
				f"neural_regularized_objective={self.settings.objective.value} requires >= {required} "
				f"OUT images per test fold / validation, got {min_out_images} "
				f"({min_pairs} pairs x K={data.images_per_shadow})"
			)

	# 試行をしてスコアを返す
	def _run_trial(
		self, trial: optuna.Trial, data: PairedShadowFeatures, splits: list[PairSplit]
	) -> float:
		params = ArchitectureParams.from_trial(trial)	# optunaのサンプラーによってパラメータ決定
		fold_scores: list[float] = []
		fold_models: list[FoldModel] = []
		# K-fold
		for split in splits:
			# 学習
			fold_model = train_with_early_stopping(
				params,
				data.subset(split.train_idx),
				data.subset(split.val_idx),
				self.settings,
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
					f"neural_regularized trial {trial.number} pruned at fold {split.fold} "
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
		trial.set_user_attr("best_epochs", result.best_epochs)
		trial.set_user_attr("cv_mean", result.mean)
		trial.set_user_attr("cv_std", result.std)
		# 全 trial の fold モデルを保持するとメモリを食うため、最良値を更新した trial のみ保持する
		if self._best is None or result.score > self._best.score:
			self._best = result
		self.logger.info(
			f"neural_regularized trial {trial.number}: score={result.score:.4f} "
			f"(mean={result.mean:.4f}, std={result.std:.4f}) params={params.to_dict()}"
		)
		return result.score

	def _save_outputs(self, study: optuna.Study, splits: list[PairSplit]) -> None:
		assert self._best is not None
		output_dir = os.path.join(self.save_dir, cfg.NEURAL_REGULARIZED_CV_DIR)
		os.makedirs(output_dir, exist_ok=True)

		study.trials_dataframe().to_csv(os.path.join(output_dir, "trials.csv"), index=False)
		with open(os.path.join(output_dir, "best_params.json"), "w") as f:
			json.dump({
				"trial_number": self._best.trial_number,
				"objective": self.settings.objective.value,
				"stability_lambda": self.settings.stability_lambda,
				"standardize": self.settings.standardize,
				"cv_score": self._best.score,
				"cv_mean": self._best.mean,
				"cv_std": self._best.std,
				**self._best.params.to_dict(),
			}, f, indent=2)
		with open(os.path.join(output_dir, "folds.json"), "w") as f:
			json.dump([
				{
					"fold": split.fold,
					"score": score,
					"best_epoch": model.best_epoch,
					"train_pairs": split.train_idx.tolist(),
					"val_pairs": split.val_idx.tolist(),
					"test_pairs": split.test_idx.tolist(),
				}
				for split, score, model in zip(
					splits, self._best.fold_scores, self._best.fold_models, strict=True
				)
			], f, indent=2)
		self.logger.info(f"neural_regularized CV results saved -> {output_dir}")

	def _build_diagnostics(self, study: optuna.Study) -> dict[str, Any]:
		assert self._best is not None
		states = [t.state for t in study.trials]
		best_params = self._best.params
		return {
			"cv_objective": self.settings.objective.value,
			"standardize": self.settings.standardize,
			"cv_score": self._best.score,
			"cv_fold_mean": self._best.mean,
			"cv_fold_std": self._best.std,
			"best_trial_number": self._best.trial_number,
			"best_lr": best_params.lr,
			"best_weight_decay": best_params.weight_decay,
			"best_n_hidden": 0 if best_params.hidden_dim is None else 1,
			# 隠れ層 0 層のときは未定義（None）
			"best_hidden_dim": best_params.hidden_dim,
			"best_dropout": best_params.dropout,
			"best_epoch_median": float(np.median(self._best.best_epochs)),
			"n_trials_completed": states.count(optuna.trial.TrialState.COMPLETE),
			"n_trials_pruned": states.count(optuna.trial.TrialState.PRUNED),
		}
