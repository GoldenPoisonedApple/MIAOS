"""
統計系メンバシップ推定で使うクラスの選択。

shadow_pair 分析と同じ判定（K 枚平均したペア差分 IN−OUT のクラス別両側 Wilcoxon 検定 +
多重比較補正）で有意なクラスだけを残すマスクを作る。非有意クラスは各スコアラーで無視する。
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from src.attacks.analysis.shadow_pair_effect_analysis import (
	bh_fdr_significant,
	bonferroni_significant,
	class_wilcoxon_pvalues,
)

logger = logging.getLogger(__name__)

# shadow_pair 分析と同じ有意水準
SIGNIFICANT_CLASS_ALPHA = 0.05


class SignificantClassSelection(str, Enum):
	"""学習・推論に使うクラスの選び方。"""

	# 全クラスを使う（従来どおり）
	NONE = "none"
	# BH-FDR で有意なクラスのみ
	BH_FDR = "bh_fdr"
	# Bonferroni で有意なクラスのみ
	BONFERRONI = "bonferroni"


DEFAULT_SIGNIFICANT_CLASS_SELECTION = SignificantClassSelection.NONE


@dataclass(frozen=True)
class ClassMask:
	"""
	使うクラスのマスク (C,)。
	fallback: 有意クラスが 0 件だったため全クラスに戻したか
	"""

	mask: np.ndarray
	selection: SignificantClassSelection
	fallback: bool = False

	def __post_init__(self) -> None:
		if self.mask.ndim != 1 or self.mask.dtype != bool:
			raise ValueError(f"mask must be 1D bool array, got {self.mask.dtype} ndim={self.mask.ndim}")

	@property
	def num_selected(self) -> int:
		return int(self.mask.sum())

	def broadcast(self, num_images: int) -> np.ndarray:
		"""(K, C) に広げる。クラス c が有意なら全画像 k の (k, c) を使う。"""
		return np.broadcast_to(self.mask, (num_images, self.mask.shape[0])).copy()

	def diagnostics(self) -> dict[str, Any]:
		return {
			"significant_class_selection": self.selection.value,
			"num_selected_classes": self.num_selected,
			"class_selection_fallback": self.fallback,
		}


def select_significant_classes(
	in_feats: np.ndarray,
	out_feats: np.ndarray,
	selection: SignificantClassSelection,
	alpha: float = SIGNIFICANT_CLASS_ALPHA,
) -> ClassMask:
	"""
	in_feats, out_feats: (n_pairs, K, C)。K 枚平均したペア差分でクラス別に有意判定する。
	有意クラスが 0 件（n_pairs < 6 で p 値が出ない場合を含む）なら警告を出して全クラスを使う。
	"""
	selection = SignificantClassSelection(selection)
	num_classes = in_feats.shape[2]
	all_classes = np.ones(num_classes, dtype=bool)
	if selection == SignificantClassSelection.NONE:
		return ClassMask(mask=all_classes, selection=selection)

	# shadow_pair 分析と同じく K 枚平均したペア差分 (n_pairs, C) で検定する
	diffs = in_feats.mean(axis=1) - out_feats.mean(axis=1)
	p_values = class_wilcoxon_pvalues(diffs)
	if selection == SignificantClassSelection.BONFERRONI:
		mask = bonferroni_significant(p_values, alpha)
	else:
		mask = bh_fdr_significant(p_values, alpha)

	if not mask.any():
		logger.warning(
			f"significant_class_selection={selection.value}: no significant class "
			f"(n_pairs={diffs.shape[0]}, alpha={alpha}); falling back to all classes"
		)
		return ClassMask(mask=all_classes, selection=selection, fallback=True)
	return ClassMask(mask=mask, selection=selection)
