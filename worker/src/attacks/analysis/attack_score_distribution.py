"""LF_MIA 系ターゲットモデルごとの攻撃スコア分布（K 枚分の IN 確率）の可視化。

各ターゲット（装飾適用率 fraction ごと）について K 枚分の IN 確率を
重ね描きヒストグラム・Facet ヒストグラム・バイオリンプロットとして
``attack_score_distribution/`` に出力し、生データを scores.json に保存する。

配色: IN (fraction>0) は fraction の順位に応じて濃い赤 → 淡い赤、OUT (fraction=0) は一律に青。
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_hex

# fraction=1.0 に割り当てる最も彩度の高い赤
IN_COLOR_STRONGEST = np.array([1.0, 0.0, 0.0])
# 最も小さい fraction に割り当てる淡い赤（白背景で視認できる下限）
IN_COLOR_PALEST = np.array([1.0, 0.72, 0.72])
# OUT (fraction=0) の色
OUT_COLOR = "#1f4fd8"
# ヒストグラムの bin 数（IN 確率 [0, 1] を等分）
HIST_BINS = 40
# Facet の列数
FACET_NCOLS = 4


@dataclass(frozen=True)
class TargetScoreEntry:
	"""1 ターゲットモデル分の K 枚の IN 確率。"""

	fraction: float
	# K 枚分の IN 確率 (K,)
	scores: np.ndarray

	@property
	def is_in(self) -> bool:
		return self.fraction > 0

	@property
	def mean(self) -> float:
		return float(np.mean(self.scores))

	@property
	def var(self) -> float:
		# K=1 では標本分散が定義できないため 0.0 とする（aggregate_scores と同じ規約）
		if self.scores.size < 2:
			return 0.0
		return float(np.var(self.scores, ddof=1))


def _ordered(entries: list[TargetScoreEntry]) -> list[TargetScoreEntry]:
	"""IN を fraction の降順、その後に OUT を元の順で並べる。"""
	ins = sorted((e for e in entries if e.is_in), key=lambda e: -e.fraction)
	outs = [e for e in entries if not e.is_in]
	return ins + outs


def target_colors(entries: list[TargetScoreEntry]) -> list[str]:
	"""
	各ターゲットの色を返す（entries と同じ順序）。
	IN は fraction の降順で順位を付け、濃い赤から淡い赤へ等間隔に割り当てる。
	"""
	in_fractions = sorted({e.fraction for e in entries if e.is_in}, reverse=True)
	n_in = len(in_fractions)
	rank_of = {f: i for i, f in enumerate(in_fractions)}

	colors: list[str] = []
	for entry in entries:
		if not entry.is_in:
			colors.append(OUT_COLOR)
			continue
		t = rank_of[entry.fraction] / (n_in - 1) if n_in > 1 else 0.0
		rgb = IN_COLOR_STRONGEST + t * (IN_COLOR_PALEST - IN_COLOR_STRONGEST)
		colors.append(to_hex(rgb))
	return colors


def target_labels(entries: list[TargetScoreEntry]) -> list[str]:
	"""IN は `IN fraction=0.5`、OUT は出現順に `OUT #1` ... を返す。"""
	labels: list[str] = []
	out_idx = 0
	for entry in entries:
		if entry.is_in:
			labels.append(f"IN fraction={entry.fraction}")
		else:
			out_idx += 1
			labels.append(f"OUT #{out_idx}")
	return labels


def _legend_labels(entries: list[TargetScoreEntry]) -> list[str]:
	"""重ね描き用の凡例ラベル。OUT は 1 項目にまとめ、2 体目以降は凡例に出さない。"""
	n_out = sum(1 for e in entries if not e.is_in)
	labels: list[str] = []
	out_seen = False
	for entry in entries:
		if entry.is_in:
			labels.append(f"IN fraction={entry.fraction}")
		elif not out_seen:
			labels.append(f"OUT fraction=0 (n={n_out})")
			out_seen = True
		else:
			labels.append("_nolegend_")
	return labels


def _normal_pdf(x: np.ndarray, mean: float, var: float) -> np.ndarray:
	return np.exp(-((x - mean) ** 2) / (2.0 * var)) / math.sqrt(2.0 * math.pi * var)


def _draw_target(
	ax: plt.Axes,
	entry: TargetScoreEntry,
	color: str,
	label: str,
	bins: np.ndarray,
	x_grid: np.ndarray,
) -> float:
	"""ヒストグラム・mean 縦線・N(mean, var) 曲線を描画し、ヒストグラムの最大密度を返す。"""
	heights, _, _ = ax.hist(
		entry.scores,
		bins=bins,
		density=True,
		histtype="stepfilled",
		facecolor=color,
		edgecolor=color,
		alpha=0.25,
		linewidth=1.0,
	)
	# 輪郭線は塗りより濃く描いて重なっても判別できるようにする
	# 凡例は淡い塗りだと判別できないため、輪郭線側に label を付ける
	ax.hist(
		entry.scores,
		bins=bins,
		density=True,
		histtype="step",
		color=color,
		linewidth=1.0,
		alpha=0.9,
		label=label,
	)
	ax.axvline(entry.mean, color=color, linestyle="--", linewidth=1.2)
	# var=0 のときは正規分布が定義できないため省略
	if entry.var > 0:
		ax.plot(x_grid, _normal_pdf(x_grid, entry.mean, entry.var), color=color, linewidth=1.2)
	return float(np.max(heights)) if len(heights) else 0.0


def plot_overlay_histogram(entries: list[TargetScoreEntry], output_path: Path) -> None:
	"""全ターゲットのヒストグラムを 1 枚に重ね描きする。"""
	entries = _ordered(entries)
	colors = target_colors(entries)
	labels = _legend_labels(entries)
	bins = np.linspace(0.0, 1.0, HIST_BINS + 1)
	x_grid = np.linspace(0.0, 1.0, 500)

	fig, ax = plt.subplots(figsize=(12, 6))
	max_height = 0.0
	for entry, color, label in zip(entries, colors, labels, strict=True):
		max_height = max(max_height, _draw_target(ax, entry, color, label, bins, x_grid))

	ax.set_xlim(0.0, 1.0)
	# 分散の小さいターゲットの正規分布曲線が突出して他が潰れないよう、ヒストグラム基準で上限を決める
	if max_height > 0:
		ax.set_ylim(0.0, max_height * 1.1)
	ax.set_xlabel("IN probability (attack score)")
	ax.set_ylabel("Density")
	ax.set_title("Attack score distribution per target (dashed: mean, solid: N(mean, var))")
	ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
	ax.grid(True, ls="--", alpha=0.4)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def plot_facet_histogram(entries: list[TargetScoreEntry], output_path: Path) -> None:
	"""ターゲットごとに小さなサブプロット（4 列。24 ターゲットで 6x4）に描画する。"""
	entries = _ordered(entries)
	colors = target_colors(entries)
	labels = target_labels(entries)
	bins = np.linspace(0.0, 1.0, HIST_BINS + 1)
	x_grid = np.linspace(0.0, 1.0, 500)

	nrows = math.ceil(len(entries) / FACET_NCOLS)
	fig, axes = plt.subplots(
		nrows, FACET_NCOLS, figsize=(4 * FACET_NCOLS, 2.6 * nrows), sharex=True, squeeze=False
	)
	flat_axes = axes.flatten()
	for ax, entry, color, label in zip(flat_axes, entries, colors, labels):
		max_height = _draw_target(ax, entry, color, label, bins, x_grid)
		if max_height > 0:
			ax.set_ylim(0.0, max_height * 1.1)
		ax.set_xlim(0.0, 1.0)
		ax.set_title(f"{label}\nmean={entry.mean:.3f}, var={entry.var:.4f}", fontsize=9)
		ax.grid(True, ls="--", alpha=0.4)
	# 余ったサブプロットは非表示
	for ax in flat_axes[len(entries):]:
		ax.set_visible(False)

	fig.supxlabel("IN probability (attack score)")
	fig.supylabel("Density")
	fig.suptitle("Attack score distribution per target (dashed: mean, solid: N(mean, var))")
	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def plot_violin(entries: list[TargetScoreEntry], output_path: Path) -> None:
	"""全ターゲットのスコア分布をバイオリンプロットで 1 枚に並べる。"""
	entries = _ordered(entries)
	colors = target_colors(entries)
	labels = target_labels(entries)
	positions = np.arange(1, len(entries) + 1)

	fig, ax = plt.subplots(figsize=(max(10, 0.6 * len(entries)), 6))
	# 全値が同一のターゲットは KDE が定義できないため、バイオリンの代わりに横線で示す
	varying = [i for i, e in enumerate(entries) if np.ptp(e.scores) > 0]
	if varying:
		parts = ax.violinplot(
			[entries[i].scores for i in varying],
			positions=positions[varying],
			showextrema=False,
			widths=0.8,
		)
		for body, i in zip(parts["bodies"], varying):
			body.set_facecolor(colors[i])
			body.set_edgecolor(colors[i])
			body.set_alpha(0.6)
	for i, entry in enumerate(entries):
		if i not in varying:
			ax.hlines(entry.scores[0], positions[i] - 0.3, positions[i] + 0.3, color=colors[i], linewidth=2)
		ax.scatter(positions[i], entry.mean, color="black", marker="_", s=200, zorder=3)

	ax.set_xticks(positions)
	ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=8)
	ax.set_ylim(-0.02, 1.02)
	ax.set_ylabel("IN probability (attack score)")
	ax.set_title("Attack score distribution per target (black bar: mean)")
	ax.grid(True, axis="y", ls="--", alpha=0.4)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_scores_json(entries: list[TargetScoreEntry], output_path: Path) -> None:
	"""fraction・mean・var・K 枚分のスコアを JSON に保存する（事後解析用）。"""
	labels = target_labels(entries)
	payload = {
		"entries": [
			{
				"label": label,
				"fraction": entry.fraction,
				"mean": entry.mean,
				"var": entry.var,
				"scores": [float(v) for v in entry.scores],
			}
			for entry, label in zip(entries, labels, strict=True)
		]
	}
	with open(output_path, "w", encoding="utf-8") as f:
		json.dump(payload, f, indent=2, ensure_ascii=False)


def analyze_attack_score_distribution(
	entries: list[TargetScoreEntry],
	output_dir: str | Path,
) -> Path:
	"""
	スコア分布の図と scores.json を出力する。
	分布図は全ターゲットで K>=2 のときのみ出力する（K=1 では分布が意味を持たない）。

	Returns:
		scores.json のパス
	"""
	model_dir = Path(output_dir)
	model_dir.mkdir(parents=True, exist_ok=True)

	scores_path = model_dir / "scores.json"
	save_scores_json(entries, scores_path)

	if entries and min(e.scores.size for e in entries) >= 2:
		plot_overlay_histogram(entries, model_dir / "histogram_overlay.png")
		plot_facet_histogram(entries, model_dir / "histogram_facet.png")
		plot_violin(entries, model_dir / "violin.png")

	return scores_path
