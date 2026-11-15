import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import optuna
import torch
import torch.nn as nn

import src.core.config as cfg
from src.attacks.membership_scorers.base import MembershipScore, ScoreScale, ShadowPairFeatures
from src.attacks.membership_scorers.pair_cv import (
	CvObjective,
	CvResult,
	CvSettings,
	LabeledSamples,
	PairCvSearch,
)
from src.models.attack_model import BinaryAttackNet

# 探索空間（固定）
LR_RANGE: tuple[float, float] = (1e-5, 1e-3)
WEIGHT_DECAY_RANGE: tuple[float, float] = (1e-5, 1e-1)
HIDDEN_DIM_RANGE: tuple[int, int] = (8, 128)
DROPOUT_RANGE: tuple[float, float] = (0.0, 0.5)


@dataclass(frozen=True)
class NeuralRegularizedSettings:
	"""neural_regularized 固有の早期停止 / 学習の設定（CV / 探索の設定は CvSettings）。"""

	patience: int = 20
	max_epochs: int = 500
	batch_size: int = cfg.ATTACK_MODEL_BATCH_SIZE
	# 入力を fold の学習側で z-score 標準化するか（False では恒等変換）
	standardize: bool = True

	def __post_init__(self) -> None:
		if self.patience < 1:
			raise ValueError(f"patience must be >= 1, got {self.patience}")
		if self.max_epochs < 1:
			raise ValueError(f"max_epochs must be >= 1, got {self.max_epochs}")
		if self.batch_size < 1:
			raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")
		if not isinstance(self.standardize, bool):
			raise ValueError(f"standardize must be bool, got {self.standardize!r}")


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

	@property
	def best_iteration(self) -> int:
		return self.best_epoch

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
	objective: CvObjective,
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
		val_metric = objective.evaluate(val_probs, val)
  
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
class NeuralFoldTrainer:
	"""neural_regularized の探索空間と 1 fold 分の学習。"""

	settings: NeuralRegularizedSettings
	objective: CvObjective

	def params_from_trial(self, trial: optuna.Trial) -> ArchitectureParams:
		return ArchitectureParams.from_trial(trial)

	def train(
		self, params: ArchitectureParams, train: LabeledSamples, val: LabeledSamples, seed: int
	) -> FoldModel:
		return train_with_early_stopping(params, train, val, self.settings, self.objective, seed)


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
		cv_settings: CvSettings,
		settings: NeuralRegularizedSettings,
		seed: int,
		save_dir: str,
		logger: logging.Logger,
	) -> None:
		self.cv_settings = cv_settings
		self.settings = settings
		self.seed = seed
		self.save_dir = save_dir
		self.logger = logger
		self._best: CvResult[ArchitectureParams, FoldModel] | None = None
		self._diagnostics: dict[str, Any] = {}

	def fit(self, features: ShadowPairFeatures) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。K 枚それぞれを独立した学習サンプルとして展開する。"""
		search = PairCvSearch(
			name=self.name,
			settings=self.cv_settings,
			trainer=NeuralFoldTrainer(settings=self.settings, objective=self.cv_settings.objective),
			seed=self.seed,
			output_dir=os.path.join(self.save_dir, cfg.NEURAL_REGULARIZED_CV_DIR),
			logger=self.logger,
			iteration_label="best_epoch",
			metadata={"standardize": self.settings.standardize},
		)
		self._best = None
		outcome = search.run(features)
		self._best = outcome.best
		best_params = outcome.best.params
		self._diagnostics = {
			**outcome.common_diagnostics(self.cv_settings.objective),
			"standardize": self.settings.standardize,
			"best_lr": best_params.lr,
			"best_weight_decay": best_params.weight_decay,
			"best_n_hidden": 0 if best_params.hidden_dim is None else 1,
			# 隠れ層 0 層のときは未定義（None）
			"best_hidden_dim": best_params.hidden_dim,
			"best_dropout": best_params.dropout,
			"best_epoch_median": float(np.median(outcome.best.best_iterations)),
			**outcome.trial_state_counts(),
		}

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: K 枚の IN 確率の平均, per_image: (K,) fold モデルのアンサンブル IN 確率"""
		if self._best is None:
			raise RuntimeError("NeuralRegularizedMembershipScorer.fit must be called before score")

		x = np.ascontiguousarray(feats, dtype=np.float32)	# float32に変換、メモリ上の連続した位置に配置
		# CV bagging: 最もスコアが良かったtrialのk-foldの複数のモデルをそのままアンサンブルして推論に使用
		per_image = self._best.predict_proba(x)
		# スコアは平均とする
		return MembershipScore(value=float(per_image.mean()), per_image=per_image)

	def diagnostics(self) -> dict[str, Any]:
		return dict(self._diagnostics)
