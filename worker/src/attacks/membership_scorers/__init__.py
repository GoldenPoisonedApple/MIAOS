import logging
from dataclasses import dataclass, field
from typing import Any

import src.core.config as cfg
from src.attacks.membership_scorers.base import (
	MembershipScore,
	MembershipScorer,
	ScoreScale,
)
from src.attacks.membership_scorers.diagonal_lda import (
	DEFAULT_DIAGONAL_LDA_REG_LAMBDA,
	DiagonalLdaMembershipScorer,
	DiagonalVariance,
)
from src.attacks.membership_scorers.flat_diagonal_lda import (
	DEFAULT_FLAT_DIAGONAL_LDA_VARIANCE,
	FlatDiagonalLdaMembershipScorer,
)
from src.attacks.membership_scorers.gaussian_lr import (
	DEFAULT_GAUSSIAN_LR_VAR_FLOOR,
	DEFAULT_GAUSSIAN_LR_VARIANCE,
	GaussianLrMembershipScorer,
	GaussianVariance,
)
from src.attacks.membership_scorers.neural import NeuralMembershipScorer
from src.attacks.membership_scorers.neural_regularized import (
	CvObjective,
	NeuralRegularizedMembershipScorer,
	NeuralRegularizedSettings,
)


# hyperparameters.membership_scorer で指定する値
MEMBERSHIP_SCORER_NEURAL = NeuralMembershipScorer.name
MEMBERSHIP_SCORER_NEURAL_REGULARIZED = NeuralRegularizedMembershipScorer.name
MEMBERSHIP_SCORER_DIAGONAL_LDA = DiagonalLdaMembershipScorer.name
MEMBERSHIP_SCORER_FLAT_DIAGONAL_LDA = FlatDiagonalLdaMembershipScorer.name
MEMBERSHIP_SCORER_GAUSSIAN_LR = GaussianLrMembershipScorer.name

VALID_MEMBERSHIP_SCORERS = frozenset({
	MEMBERSHIP_SCORER_NEURAL,
	MEMBERSHIP_SCORER_NEURAL_REGULARIZED,
	MEMBERSHIP_SCORER_DIAGONAL_LDA,
	MEMBERSHIP_SCORER_FLAT_DIAGONAL_LDA,
	MEMBERSHIP_SCORER_GAUSSIAN_LR,
})


@dataclass(frozen=True)
class MembershipScorerConfig:
	"""攻撃モデルの種別とハイパーパラメータ。"""

	kind: str = MEMBERSHIP_SCORER_NEURAL
	# diagonal_lda / flat_diagonal_lda で共用する正則化項
	diagonal_lda_reg_lambda: float = DEFAULT_DIAGONAL_LDA_REG_LAMBDA
	flat_diagonal_lda_variance: DiagonalVariance = DEFAULT_FLAT_DIAGONAL_LDA_VARIANCE
	gaussian_lr_variance: GaussianVariance = DEFAULT_GAUSSIAN_LR_VARIANCE
	gaussian_lr_var_floor: float = DEFAULT_GAUSSIAN_LR_VAR_FLOOR
	attack_model_batch_size: int = cfg.ATTACK_MODEL_BATCH_SIZE
	attack_model_epochs: int = cfg.ATTACK_MODEL_EPOCHS
	# neural_regularized 用（不変条件は NeuralRegularizedSettings 側で検証）
	neural_regularized: NeuralRegularizedSettings = field(default_factory=NeuralRegularizedSettings)

	def __post_init__(self) -> None:
		if self.kind not in VALID_MEMBERSHIP_SCORERS:
			raise ValueError(
				f"Invalid membership_scorer={self.kind!r}; "
				f"expected one of {sorted(VALID_MEMBERSHIP_SCORERS)}"
			)
		# 文字列で渡された場合も Enum に正規化する（不正値はここで ValueError）
		object.__setattr__(
			self,
			"flat_diagonal_lda_variance",
			_parse_enum(DiagonalVariance, self.flat_diagonal_lda_variance, "flat_diagonal_lda_variance"),
		)
		object.__setattr__(
			self,
			"gaussian_lr_variance",
			_parse_enum(GaussianVariance, self.gaussian_lr_variance, "gaussian_lr_variance"),
		)
		if self.gaussian_lr_var_floor <= 0:
			raise ValueError(
				f"gaussian_lr_var_floor must be positive, got {self.gaussian_lr_var_floor}"
			)

	@classmethod
	def from_hyperparameters(cls, hp: dict[str, Any] | None) -> "MembershipScorerConfig":
		"""
		membership_scorer: neural（デフォルト）| neural_regularized | diagonal_lda | flat_diagonal_lda | gaussian_lr
		diagonal_lda_reg_lambda: diagonal_lda / flat_diagonal_lda 用。未指定時 DEFAULT_DIAGONAL_LDA_REG_LAMBDA
		flat_diagonal_lda_variance: within_class（デフォルト）| pair_diff
		gaussian_lr_variance: per_class（デフォルト）| pooled
		gaussian_lr_var_floor: gaussian_lr の分散の下限。未指定時 DEFAULT_GAUSSIAN_LR_VAR_FLOOR
		attack_model_batch_size / attack_model_epochs: neural 用。未指定時 cfg の既定値
			（attack_model_batch_size は neural_regularized でも使用）
		neural_regularized_*: neural_regularized 用。未指定時 NeuralRegularizedSettings の既定値
		"""
		if not hp:
			return cls()
		batch_size = int(hp.get("attack_model_batch_size", cfg.ATTACK_MODEL_BATCH_SIZE))
		defaults = NeuralRegularizedSettings()
		neural_regularized = NeuralRegularizedSettings(
			objective=_parse_enum(
				CvObjective,
				hp.get("neural_regularized_objective", defaults.objective),
				"neural_regularized_objective",
			),
			n_folds=int(hp.get("neural_regularized_n_folds", defaults.n_folds)),
			val_ratio=float(hp.get("neural_regularized_val_ratio", defaults.val_ratio)),
			n_trials=int(hp.get("neural_regularized_n_trials", defaults.n_trials)),
			stability_lambda=float(
				hp.get("neural_regularized_stability_lambda", defaults.stability_lambda)
			),
			patience=int(hp.get("neural_regularized_patience", defaults.patience)),
			max_epochs=int(hp.get("neural_regularized_max_epochs", defaults.max_epochs)),
			batch_size=batch_size,
		)
		return cls(
			kind=str(hp.get("membership_scorer", MEMBERSHIP_SCORER_NEURAL)).strip().lower(),
			diagonal_lda_reg_lambda=float(
				hp.get("diagonal_lda_reg_lambda", DEFAULT_DIAGONAL_LDA_REG_LAMBDA)
			),
			flat_diagonal_lda_variance=hp.get(
				"flat_diagonal_lda_variance", DEFAULT_FLAT_DIAGONAL_LDA_VARIANCE
			),
			gaussian_lr_variance=hp.get("gaussian_lr_variance", DEFAULT_GAUSSIAN_LR_VARIANCE),
			gaussian_lr_var_floor=float(
				hp.get("gaussian_lr_var_floor", DEFAULT_GAUSSIAN_LR_VAR_FLOOR)
			),
			attack_model_batch_size=batch_size,
			attack_model_epochs=int(hp.get("attack_model_epochs", cfg.ATTACK_MODEL_EPOCHS)),
			neural_regularized=neural_regularized,
		)


def _parse_enum(enum_cls: type, value: Any, key: str):
	"""Enum またはその値の文字列を Enum に変換する。"""
	if isinstance(value, enum_cls):
		return value
	normalized = str(value).strip().lower()
	try:
		return enum_cls(normalized)
	except ValueError as e:
		raise ValueError(
			f"Invalid {key}={value!r}; expected one of {sorted(m.value for m in enum_cls)}"
		) from e


def build_membership_scorer(
	config: MembershipScorerConfig,
	*,
	save_dir: str,
	logger: logging.Logger,
	seed: int,
) -> MembershipScorer:
	if config.kind == MEMBERSHIP_SCORER_NEURAL_REGULARIZED:
		return NeuralRegularizedMembershipScorer(
			settings=config.neural_regularized,
			seed=seed,
			save_dir=save_dir,
			logger=logger,
		)
	if config.kind == MEMBERSHIP_SCORER_DIAGONAL_LDA:
		return DiagonalLdaMembershipScorer(reg_lambda=config.diagonal_lda_reg_lambda)
	if config.kind == MEMBERSHIP_SCORER_FLAT_DIAGONAL_LDA:
		return FlatDiagonalLdaMembershipScorer(
			reg_lambda=config.diagonal_lda_reg_lambda,
			variance=config.flat_diagonal_lda_variance,
		)
	if config.kind == MEMBERSHIP_SCORER_GAUSSIAN_LR:
		return GaussianLrMembershipScorer(
			variance=config.gaussian_lr_variance,
			var_floor=config.gaussian_lr_var_floor,
		)
	return NeuralMembershipScorer(
		save_dir=save_dir,
		logger=logger,
		batch_size=config.attack_model_batch_size,
		epochs=config.attack_model_epochs,
	)


__all__ = [
	"MEMBERSHIP_SCORER_DIAGONAL_LDA",
	"MEMBERSHIP_SCORER_FLAT_DIAGONAL_LDA",
	"MEMBERSHIP_SCORER_GAUSSIAN_LR",
	"MEMBERSHIP_SCORER_NEURAL",
	"MEMBERSHIP_SCORER_NEURAL_REGULARIZED",
	"MembershipScore",
	"MembershipScorer",
	"MembershipScorerConfig",
	"ScoreScale",
	"build_membership_scorer",
]
