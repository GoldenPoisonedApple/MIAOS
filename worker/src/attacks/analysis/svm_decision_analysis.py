"""svm / flat_svm の学習済みモデルの可視化。

- pca_scatter.png: シャドー全体で fit した z-score 標準化 + PCA(2) の平面に、シャドー IN/OUT と
  ターゲット（同じ変換で射影）を描く
- decision_histogram.png: Platt 較正後 logit の分布。シャドーは out-of-fold、ターゲットは fold アンサンブル
- summary.json: PCA の寄与率、点の数、群ごとの logit の平均・標準偏差、シャドーの OOF AUC

配色は attack_score_distribution と揃える: IN は赤系、OUT は青。
"""

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap, LogNorm
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

from src.attacks.membership_scorers.base import DecisionAnalysisData

SHADOW_IN_COLOR = "#f08080"
SHADOW_OUT_COLOR = "#7fa7f0"
TARGET_IN_COLOR = "#c00000"
TARGET_OUT_COLOR = "#1f4fd8"
# ターゲット IN の適用率のカラーマップ（適用率は 1.0〜0.001 と桁が違うため対数で色付けする）
# 白背景で最小の適用率も視認できるよう、Reds の淡い側を切り落とす
TARGET_FRACTION_CMAP = ListedColormap(plt.get_cmap("Reds")(np.linspace(0.3, 1.0, 256)))
PCA_COMPONENTS = 2
HIST_BINS = 40


def _shadow_alpha(n_points: int) -> float:
	"""点が多い（画像単位）ほど薄くして重なりを見えるようにする"""
	return float(np.clip(200.0 / max(n_points, 1), 0.05, 0.7))


def _fraction_norm(fractions: np.ndarray) -> LogNorm:
	"""IN ターゲットの適用率 (> 0) の対数カラースケール。全て同じ値のときは幅 1 桁の範囲を取る"""
	lo, hi = float(fractions.min()), float(fractions.max())
	return LogNorm(vmin=lo, vmax=hi if hi > lo else lo * 10)


def fit_pca_projection(
	data: DecisionAnalysisData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
	"""シャドーで fit した標準化 + PCA で、シャドーとターゲットを射影する。戻り値: (shadow_2d, target_2d, 寄与率)"""
	scaler = StandardScaler().fit(data.shadow_x)
	shadow_z = scaler.transform(data.shadow_x)
	n_components = min(PCA_COMPONENTS, shadow_z.shape[0], shadow_z.shape[1])
	pca = PCA(n_components=n_components).fit(shadow_z)
	shadow_2d = pca.transform(shadow_z)
	target_2d = pca.transform(scaler.transform(data.target_x))
	ratio = pca.explained_variance_ratio_
	# 次元・サンプルが 1 のときも 2 軸で描けるよう 0 で埋める
	if n_components < PCA_COMPONENTS:
		pad = PCA_COMPONENTS - n_components
		shadow_2d = np.pad(shadow_2d, ((0, 0), (0, pad)))
		target_2d = np.pad(target_2d, ((0, 0), (0, pad)))
		ratio = np.pad(ratio, (0, pad))
	return shadow_2d, target_2d, ratio


def plot_pca_scatter(
	data: DecisionAnalysisData,
	shadow_2d: np.ndarray,
	target_2d: np.ndarray,
	ratio: np.ndarray,
	output_path: Path,
) -> None:
	is_in = data.shadow_y == 1
	target_in = data.target_fraction > 0
	alpha = _shadow_alpha(len(data.shadow_y))

	fig, ax = plt.subplots(figsize=(9, 7))
	ax.scatter(*shadow_2d[~is_in].T, s=10, c=SHADOW_OUT_COLOR, alpha=alpha, label="shadow OUT")
	ax.scatter(*shadow_2d[is_in].T, s=10, c=SHADOW_IN_COLOR, alpha=alpha, label="shadow IN")
	ax.scatter(
		*target_2d[~target_in].T, s=60, marker="^", c=TARGET_OUT_COLOR,
		edgecolors="black", linewidths=0.6, label="target OUT (fraction=0)",
	)
	if target_in.any():
		fractions = data.target_fraction[target_in]
		points = ax.scatter(
			*target_2d[target_in].T, s=60, marker="^", c=fractions, cmap=TARGET_FRACTION_CMAP,
			norm=_fraction_norm(fractions),
			edgecolors="black", linewidths=0.6, label="target IN (color: fraction)",
		)
		fig.colorbar(points, ax=ax, label="target fraction (log)")

	ax.set_xlabel(f"PC1 ({ratio[0]:.1%})")
	ax.set_ylabel(f"PC2 ({ratio[1]:.1%})")
	ax.set_title(f"{data.scorer_name}: PCA of standardized input (unit={data.unit})")
	ax.legend(loc="best", fontsize=8)
	ax.grid(True, ls="--", alpha=0.4)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def plot_decision_histogram(data: DecisionAnalysisData, output_path: Path) -> None:
	is_in = data.shadow_y == 1
	target_in = data.target_fraction > 0
	values = np.concatenate([data.shadow_logit, data.target_logit])
	bins = np.linspace(float(values.min()), float(values.max()), HIST_BINS + 1) if np.ptp(values) > 0 else HIST_BINS

	fig, ax = plt.subplots(figsize=(10, 6))
	ax.hist(data.shadow_logit[~is_in], bins=bins, density=True, histtype="stepfilled",
		color=SHADOW_OUT_COLOR, alpha=0.4, label=f"shadow OUT, out-of-fold (n={int((~is_in).sum())})")
	ax.hist(data.shadow_logit[is_in], bins=bins, density=True, histtype="stepfilled",
		color=SHADOW_IN_COLOR, alpha=0.4, label=f"shadow IN, out-of-fold (n={int(is_in.sum())})")
	if (~target_in).any():
		ax.hist(data.target_logit[~target_in], bins=bins, density=True, histtype="step",
			color=TARGET_OUT_COLOR, linewidth=1.8, label=f"target OUT, ensemble (n={int((~target_in).sum())})")
	if target_in.any():
		ax.hist(data.target_logit[target_in], bins=bins, density=True, histtype="step",
			color=TARGET_IN_COLOR, linewidth=1.8, label=f"target IN, ensemble (n={int(target_in.sum())})")
	# ターゲットの個々の値（シャドー単位では 24 点しかなくヒストグラムだけでは読み取りにくい）
	y_rug = ax.get_ylim()[0]
	ax.plot(data.target_logit[~target_in], np.full((~target_in).sum(), y_rug), "|",
		color=TARGET_OUT_COLOR, markersize=14, markeredgewidth=1.2)
	ax.plot(data.target_logit[target_in], np.full(target_in.sum(), y_rug), "|",
		color=TARGET_IN_COLOR, markersize=14, markeredgewidth=1.2)
	ax.axvline(0.0, color="gray", linestyle=":", linewidth=1.0)

	ax.set_xlabel("Platt-calibrated logit (a * decision_function + b)")
	ax.set_ylabel("Density")
	ax.set_title(f"{data.scorer_name}: calibrated decision values (unit={data.unit})")
	ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
	ax.grid(True, ls="--", alpha=0.4)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def _stats(values: np.ndarray) -> dict[str, Any]:
	if values.size == 0:
		return {"n": 0, "mean": None, "std": None}
	return {"n": int(values.size), "mean": float(values.mean()), "std": float(values.std())}


def build_summary(data: DecisionAnalysisData, ratio: np.ndarray) -> dict[str, Any]:
	is_in = data.shadow_y == 1
	target_in = data.target_fraction > 0
	# IN / OUT の両方が無いと AUC は定義できない
	oof_auc = float(roc_auc_score(data.shadow_y, data.shadow_logit)) if 0 < is_in.sum() < is_in.size else None
	return {
		"scorer": data.scorer_name,
		"unit": data.unit,
		"num_features": int(data.shadow_x.shape[1]),
		"pca_explained_variance_ratio": [float(r) for r in ratio],
		# シャドーのサンプル単位（unit）の out-of-fold logit による AUC
		"shadow_oof_auc": oof_auc,
		"logit": {
			"shadow_in": _stats(data.shadow_logit[is_in]),
			"shadow_out": _stats(data.shadow_logit[~is_in]),
			"target_in": _stats(data.target_logit[target_in]),
			"target_out": _stats(data.target_logit[~target_in]),
		},
	}


def analyze_svm_decision(data: DecisionAnalysisData, output_dir: str | Path) -> Path:
	"""
	PCA 散布図・較正後 logit ヒストグラム・summary.json を出力する。

	Returns:
		summary.json のパス
	"""
	out = Path(output_dir)
	out.mkdir(parents=True, exist_ok=True)

	shadow_2d, target_2d, ratio = fit_pca_projection(data)
	plot_pca_scatter(data, shadow_2d, target_2d, ratio, out / "pca_scatter.png")
	plot_decision_histogram(data, out / "decision_histogram.png")

	summary_path = out / "summary.json"
	with open(summary_path, "w", encoding="utf-8") as f:
		json.dump(build_summary(data, ratio), f, indent=2, ensure_ascii=False)
	return summary_path
