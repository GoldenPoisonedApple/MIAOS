"""LF_MIA 系の画像ごとのスコアによる、IN ターゲットの装飾適用率ごとの ROC。

各パネルは適用率 f の IN ターゲットの K 枚分のスコアを陽性、fraction=0 の全 OUT ターゲットの
K 枚分のスコアを陰性とした ROC（log-log）。陰性は全パネルで共通。
"""

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.attacks.analysis.attack_score_distribution import TargetScoreEntry
from src.attacks.mia_attack import MIA_Attack

NCOLS = 4
# 既存の roc_curve_all_scores.png と同じ log-log の表示範囲
AXIS_MIN = 1e-5
TPR_AXIS_MAX = 1.05
MARKED_FPR = 0.01


def _positives_by_fraction(entries: list[TargetScoreEntry]) -> list[tuple[float, np.ndarray]]:
	"""IN ターゲットのスコアを適用率ごとにまとめ、適用率の降順に並べる"""
	fractions = sorted({e.fraction for e in entries if e.is_in}, reverse=True)
	return [
		(f, np.concatenate([e.scores for e in entries if e.fraction == f]))
		for f in fractions
	]


def plot_roc_per_fraction(entries: list[TargetScoreEntry], output_path: str | Path) -> bool:
	"""
	適用率ごとの ROC を 4 列のパネル（12 段階で 3x4）にまとめて出力する。
	K>=2 のときのみ出力する（K=1 では陽性が 1 点で ROC が意味を持たない）。

	Returns:
		出力したか（K<2、または IN / OUT のどちらかが無いときは False）
	"""
	if not entries or min(e.scores.size for e in entries) < 2:
		return False
	positives = _positives_by_fraction(entries)
	negatives = [e.scores for e in entries if not e.is_in]
	if not positives or not negatives:
		return False
	out_scores = np.concatenate(negatives)

	nrows = math.ceil(len(positives) / NCOLS)
	fig, axes = plt.subplots(
		nrows, NCOLS, figsize=(4 * NCOLS, 4 * nrows), sharex=True, sharey=True, squeeze=False
	)
	flat_axes = axes.flatten()
	for ax, (fraction, in_scores) in zip(flat_axes, positives):
		trues = np.concatenate([np.ones(in_scores.size), np.zeros(out_scores.size)])
		roc_metrics, fpr, tpr, roc_auc = MIA_Attack.compute_roc_metrics(
			trues, np.concatenate([in_scores, out_scores])
		)
		ax.plot(fpr, tpr, color="green", lw=1, marker="o", markersize=2)
		ax.plot([AXIS_MIN, 1], [AXIS_MIN, 1], color="navy", lw=1, linestyle="--")
		ax.axvline(x=MARKED_FPR, linestyle="--", linewidth=1, color="blue")
		ax.set_xscale("log")
		ax.set_yscale("log")
		ax.set_xlim([AXIS_MIN, 1.0])
		ax.set_ylim([AXIS_MIN, TPR_AXIS_MAX])
		ax.set_title(
			f"fraction={fraction}\nAUC={roc_auc:.4f}, TPR@1%FPR={roc_metrics['tpr_at_1_fpr']:.4f}",
			fontsize=10,
		)
		ax.grid(True, which="both", ls="--", alpha=0.5)
	# 余ったパネルは非表示
	for ax in flat_axes[len(positives):]:
		ax.set_visible(False)

	fig.supxlabel("False Positive Rate (FPR)")
	fig.supylabel("True Positive Rate (TPR)")
	fig.suptitle(
		f"LF MIA ROC per target fraction over per-image scores (Log-Log Scale)\n"
		f"positive: K scores of the fraction, negative: all OUT targets (n={out_scores.size}); "
		f"dashed: random guess / 1% FPR"
	)
	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)
	return True
