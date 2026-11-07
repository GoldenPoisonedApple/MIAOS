import logging
from dataclasses import dataclass
from typing import Any

import src.core.config as cfg
from src.attacks.membership_scorers.base import MembershipScorer
from src.attacks.membership_scorers.diagonal_lda import (
	DEFAULT_DIAGONAL_LDA_REG_LAMBDA,
	DiagonalLdaMembershipScorer,
)
from src.attacks.membership_scorers.neural import NeuralMembershipScorer


# hyperparameters.membership_scorer で指定する値
MEMBERSHIP_SCORER_NEURAL = NeuralMembershipScorer.name
MEMBERSHIP_SCORER_DIAGONAL_LDA = DiagonalLdaMembershipScorer.name

VALID_MEMBERSHIP_SCORERS = frozenset({
	MEMBERSHIP_SCORER_NEURAL,
	MEMBERSHIP_SCORER_DIAGONAL_LDA,
})


@dataclass(frozen=True)
class MembershipScorerConfig:
	"""攻撃モデルの種別とハイパーパラメータ。"""

	kind: str = MEMBERSHIP_SCORER_NEURAL
	diagonal_lda_reg_lambda: float = DEFAULT_DIAGONAL_LDA_REG_LAMBDA
	attack_model_batch_size: int = cfg.ATTACK_MODEL_BATCH_SIZE
	attack_model_epochs: int = cfg.ATTACK_MODEL_EPOCHS

	def __post_init__(self) -> None:
		if self.kind not in VALID_MEMBERSHIP_SCORERS:
			raise ValueError(
				f"Invalid membership_scorer={self.kind!r}; "
				f"expected one of {sorted(VALID_MEMBERSHIP_SCORERS)}"
			)

	@classmethod
	def from_hyperparameters(cls, hp: dict[str, Any] | None) -> "MembershipScorerConfig":
		"""
		membership_scorer: neural（デフォルト）| diagonal_lda
		diagonal_lda_reg_lambda: 未指定時 DEFAULT_DIAGONAL_LDA_REG_LAMBDA
		attack_model_batch_size / attack_model_epochs: neural 用。未指定時 cfg の既定値
		"""
		if not hp:
			return cls()
		return cls(
			kind=str(hp.get("membership_scorer", MEMBERSHIP_SCORER_NEURAL)).strip().lower(),
			diagonal_lda_reg_lambda=float(
				hp.get("diagonal_lda_reg_lambda", DEFAULT_DIAGONAL_LDA_REG_LAMBDA)
			),
			attack_model_batch_size=int(
				hp.get("attack_model_batch_size", cfg.ATTACK_MODEL_BATCH_SIZE)
			),
			attack_model_epochs=int(hp.get("attack_model_epochs", cfg.ATTACK_MODEL_EPOCHS)),
		)


def build_membership_scorer(
	config: MembershipScorerConfig,
	*,
	save_dir: str,
	logger: logging.Logger,
) -> MembershipScorer:
	if config.kind == MEMBERSHIP_SCORER_DIAGONAL_LDA:
		return DiagonalLdaMembershipScorer(reg_lambda=config.diagonal_lda_reg_lambda)
	return NeuralMembershipScorer(
		save_dir=save_dir,
		logger=logger,
		batch_size=config.attack_model_batch_size,
		epochs=config.attack_model_epochs,
	)


__all__ = [
	"MEMBERSHIP_SCORER_DIAGONAL_LDA",
	"MEMBERSHIP_SCORER_NEURAL",
	"MembershipScorer",
	"MembershipScorerConfig",
	"build_membership_scorer",
]
