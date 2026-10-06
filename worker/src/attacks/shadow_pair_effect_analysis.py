"""シャドー IN/OUT ペアのクラス別装飾効果量解析。

同一 seed の IN/OUT シャドーモデルに同じプローブを入力し、
クラスごとのペア差分に Wilcoxon 検定・Cohen's d・BH-FDR・
グローバル置換検定を適用する。AttackNet には依存しない。
"""

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import wilcoxon

import src.core.config as cfg
from src.attacks.attack_model_analysis import plot_signed_class_values

# Wilcoxon 符号順位検定の最小ペア数（scipy の推奨に合わせる）
_MIN_PAIRS_FOR_WILCOXON = 6


@dataclass(frozen=True)
class ShadowPairEffectResult:
	"""metrics に載せるスカラー要約。"""

	global_permutation_pvalue: float
	num_significant_bonferroni: int
	num_significant_fdr: int
	top_class_by_abs_cohens_d: int
	summary_path: Path


@dataclass(frozen=True)
class ClassEffectStats:
	"""1 クラス分のペア差分統計。"""

	mean_diff: float
	cohens_d: float | None
	wilcoxon_p: float | None


def _pair_diffs(in_features: np.ndarray, out_features: np.ndarray) -> np.ndarray:
	"""ペア差分 (n_pairs, n_classes)。"""
	return in_features - out_features


def _cohens_d_paired(diffs: np.ndarray) -> float | None:
	"""1 クラスのペア差分列に対する Cohen's d。"""
	std = float(np.std(diffs, ddof=1))
	if std == 0.0:
		return None
	return float(np.mean(diffs) / std)


def _wilcoxon_pvalue(diffs: np.ndarray, n_pairs: int) -> float | None:
	"""両側 Wilcoxon 符号順位検定の p 値。"""
	if n_pairs < _MIN_PAIRS_FOR_WILCOXON:
		return None
	if np.allclose(diffs, 0.0):
		return None
	result = wilcoxon(diffs, alternative="two-sided")
	return float(result.pvalue)


def bh_fdr_significant(p_values: np.ndarray, alpha: float) -> np.ndarray:
	"""Benjamini–Hochberg FDR 制御。有意なクラスインデックスの boolean マスクを返す。"""
	n = len(p_values)
	if n == 0:
		return np.array([], dtype=bool)

	valid = np.isfinite(p_values)
	significant = np.zeros(n, dtype=bool)
	if not valid.any():
		return significant

	valid_idx = np.where(valid)[0]
	sorted_order = valid_idx[np.argsort(p_values[valid_idx])]
	sorted_p = p_values[sorted_order]

	# 最大の k で p_(k) <= (k/n)*alpha を満たすインデックスを探す
	k_max = -1
	for k in range(len(sorted_p), 0, -1):
		threshold = (k / n) * alpha
		if sorted_p[k - 1] <= threshold:
			k_max = k
			break

	if k_max > 0:
		significant[sorted_order[:k_max]] = True
	return significant


def bh_fdr_threshold_p(p_values: np.ndarray, alpha: float) -> float | None:
	"""BH-FDR で有意と判定される最大の生 p 値（プロット用閾値線）。"""
	n = len(p_values)
	valid = np.isfinite(p_values)
	if not valid.any():
		return None

	valid_idx = np.where(valid)[0]
	sorted_order = valid_idx[np.argsort(p_values[valid_idx])]
	sorted_p = p_values[sorted_order]

	for k in range(len(sorted_p), 0, -1):
		if sorted_p[k - 1] <= (k / n) * alpha:
			return float(sorted_p[k - 1])
	return None


def global_permutation_pvalue(
	diffs: np.ndarray,
	n_permutations: int,
	random_state: int,
) -> float:
	"""符号反転置換による max |mean(diff_c)| のグローバル p 値。"""
	rng = np.random.default_rng(random_state)
	# diffs: (n_pairs, n_classes)
	observed = float(np.max(np.abs(np.mean(diffs, axis=0))))
	n_pairs = diffs.shape[0]

	null_stats = np.empty(n_permutations, dtype=np.float64)
	for b in range(n_permutations):
		signs = rng.choice([-1.0, 1.0], size=n_pairs)
		flipped = diffs * signs[:, None]
		null_stats[b] = np.max(np.abs(np.mean(flipped, axis=0)))

	count = int(np.sum(null_stats >= observed))
	return float((count + 1) / (n_permutations + 1))


def compute_class_stats(
	in_features: np.ndarray,
	out_features: np.ndarray,
	alpha: float,
) -> tuple[list[ClassEffectStats], np.ndarray, list[int], list[int]]:
	"""クラス別統計量と有意クラス ID リストを返す。"""
	diffs = _pair_diffs(in_features, out_features)
	n_pairs, n_classes = diffs.shape
	mean_diffs = np.mean(diffs, axis=0)

	stats: list[ClassEffectStats] = []
	p_values = np.full(n_classes, np.nan)

	for c in range(n_classes):
		col = diffs[:, c]
		p = _wilcoxon_pvalue(col, n_pairs)
		p_values[c] = p if p is not None else np.nan
		stats.append(
			ClassEffectStats(
				mean_diff=float(mean_diffs[c]),
				cohens_d=_cohens_d_paired(col),
				wilcoxon_p=p,
			)
		)

	valid_p = np.isfinite(p_values)
	bonferroni_ids = [
		int(c)
		for c in range(n_classes)
		if valid_p[c] and p_values[c] * n_classes < alpha
	]
	fdr_mask = bh_fdr_significant(p_values, alpha)
	fdr_ids = [int(c) for c in range(n_classes) if fdr_mask[c]]

	return stats, p_values, bonferroni_ids, fdr_ids


def _neglog10_p(p_values: np.ndarray) -> np.ndarray:
	"""p 値の -log10。非有限は NaN。"""
	out = np.full_like(p_values, np.nan, dtype=np.float64)
	finite = np.isfinite(p_values) & (p_values > 0)
	out[finite] = -np.log10(p_values[finite])
	return out


def plot_wilcoxon_neglog10_p_bar(
	mean_diffs: np.ndarray,
	p_values: np.ndarray,
	output_path: Path,
	alpha: float,
	fdr_threshold_p: float | None,
) -> None:
	"""Wilcoxon p 値の -log10 棒グラフ（Bonferroni / BH-FDR 閾値線付き）。"""
	n_classes = len(mean_diffs)
	class_ids = np.arange(n_classes)
	neglog10 = _neglog10_p(p_values)
	valid = np.isfinite(neglog10)
	colors = np.where(mean_diffs >= 0, "indianred", "steelblue")

	fig, ax = plt.subplots(figsize=(16, 5))
	if valid.any():
		ax.bar(class_ids[valid], neglog10[valid], width=0.8, color=colors[valid])
	bonf_line = -np.log10(alpha / n_classes)
	ax.axhline(bonf_line, color="black", linewidth=1.0, linestyle="-", label=f"Bonferroni ({alpha}/{n_classes})")
	if fdr_threshold_p is not None and fdr_threshold_p > 0:
		fdr_line = -np.log10(fdr_threshold_p)
		ax.axhline(fdr_line, color="gray", linewidth=1.0, linestyle="--", label="BH-FDR threshold")
	ax.set_xlim(-0.5, n_classes - 0.5)
	ax.set_xticks(class_ids[::10])
	ax.set_xticklabels([str(i) for i in class_ids[::10]])
	ax.set_xlabel("Class ID")
	ax.set_ylabel("-log10(wilcoxon_p)")
	ax.set_title(f"Wilcoxon signed-rank p-values (all {n_classes} classes, valid only)")
	ax.legend(loc="upper right", fontsize=8)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_volcano(
	mean_diffs: np.ndarray,
	p_values: np.ndarray,
	output_path: Path,
	alpha: float,
	fdr_threshold_p: float | None,
) -> None:
	"""Volcano プロット: mean_diff vs -log10(wilcoxon_p)。"""
	neglog10 = _neglog10_p(p_values)
	valid = np.isfinite(neglog10)
	n_classes = len(mean_diffs)
	colors = np.where(mean_diffs >= 0, "indianred", "steelblue")

	fig, ax = plt.subplots(figsize=(10, 6))
	if valid.any():
		ax.scatter(mean_diffs[valid], neglog10[valid], c=colors[valid], s=12, alpha=0.7)
	bonf_line = -np.log10(alpha / n_classes)
	ax.axhline(bonf_line, color="black", linewidth=1.0, linestyle="-", label=f"Bonferroni ({alpha}/{n_classes})")
	if fdr_threshold_p is not None and fdr_threshold_p > 0:
		fdr_line = -np.log10(fdr_threshold_p)
		ax.axhline(fdr_line, color="gray", linewidth=1.0, linestyle="--", label="BH-FDR threshold")
	ax.axvline(0.0, color="black", linewidth=0.5, linestyle=":")
	ax.set_xlabel("mean_diff (IN - OUT)")
	ax.set_ylabel("-log10(wilcoxon_p)")
	ax.set_title(f"Volcano plot (all {n_classes} classes, valid only)")
	ax.legend(loc="upper right", fontsize=8)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def analyze_shadow_pair_effects(
	in_features: np.ndarray,
	out_features: np.ndarray,
	output_dir: str | Path,
	random_state: int,
	alpha: float = 0.05,
	n_permutations: int | None = None,
) -> ShadowPairEffectResult:
	"""シャドー IN/OUT ペア特徴から効果量解析を実行し、PNG と summary.json を出力する。

	Args:
		in_features: (n_pairs, n_classes)
		out_features: (n_pairs, n_classes)
		output_dir: 出力ディレクトリ
		random_state: 置換検定 RNG シード
		alpha: 多重比較の有意水準
		n_permutations: 置換回数（省略時は config 定数）

	Returns:
		ShadowPairEffectResult
	"""
	if in_features.shape != out_features.shape:
		raise ValueError(
			f"in_features and out_features must have the same shape, "
			f"got {in_features.shape} vs {out_features.shape}"
		)
	if in_features.ndim != 2:
		raise ValueError(f"Expected 2D arrays, got ndim={in_features.ndim}")

	n_pairs, n_classes = in_features.shape
	if n_permutations is None:
		n_permutations = cfg.SHADOW_PAIR_N_PERMUTATIONS

	model_dir = Path(output_dir)
	model_dir.mkdir(parents=True, exist_ok=True)

	diffs = _pair_diffs(in_features, out_features)
	class_stats, p_values, bonferroni_ids, fdr_ids = compute_class_stats(
		in_features, out_features, alpha
	)
	mean_diffs = np.array([s.mean_diff for s in class_stats])
	cohens_ds = np.array(
		[s.cohens_d if s.cohens_d is not None else np.nan for s in class_stats]
	)

	global_p = global_permutation_pvalue(diffs, n_permutations, random_state)
	fdr_threshold_p = bh_fdr_threshold_p(p_values, alpha)

	abs_cohens = np.abs(cohens_ds)
	if np.any(np.isfinite(abs_cohens)):
		top_class = int(np.nanargmax(abs_cohens))
		top_cohens_d = float(cohens_ds[top_class]) if np.isfinite(cohens_ds[top_class]) else 0.0
	else:
		top_class = 0
		top_cohens_d = 0.0

	# --- 可視化 ---
	plot_signed_class_values(
		mean_diffs,
		model_dir / "mean_diff_bar.png",
		f"Shadow pair mean diff IN-OUT (all {n_classes} classes)",
		"mean_diff (+: IN, -: OUT)",
	)
	plot_signed_class_values(
		np.nan_to_num(cohens_ds, nan=0.0),
		model_dir / "cohens_d_bar.png",
		f"Shadow pair Cohen's d (all {n_classes} classes)",
		"Cohen's d (+: IN, -: OUT)",
	)
	plot_wilcoxon_neglog10_p_bar(
		mean_diffs,
		p_values,
		model_dir / "wilcoxon_neglog10_p_bar.png",
		alpha,
		fdr_threshold_p,
	)
	plot_volcano(mean_diffs, p_values, model_dir / "volcano.png", alpha, fdr_threshold_p)

	# --- summary.json ---
	classes_dict: dict[str, dict] = {}
	for c, stat in enumerate(class_stats):
		classes_dict[str(c)] = {
			"mean_diff": stat.mean_diff,
			"cohens_d": stat.cohens_d,
			"wilcoxon_p": stat.wilcoxon_p,
		}

	summary = {
		"n_pairs": n_pairs,
		"alpha": alpha,
		"n_permutations": n_permutations,
		"global_permutation_p": global_p,
		"top_class_by_abs_cohens_d": top_class,
		"top_class_cohens_d": top_cohens_d,
		"significant_class_ids_bonferroni": bonferroni_ids,
		"significant_class_ids_fdr": fdr_ids,
		"classes": classes_dict,
	}
	summary_path = model_dir / "summary.json"
	with summary_path.open("w", encoding="utf-8") as f:
		json.dump(summary, f, indent=2, ensure_ascii=False)

	return ShadowPairEffectResult(
		global_permutation_pvalue=global_p,
		num_significant_bonferroni=len(bonferroni_ids),
		num_significant_fdr=len(fdr_ids),
		top_class_by_abs_cohens_d=top_class,
		summary_path=summary_path,
	)
