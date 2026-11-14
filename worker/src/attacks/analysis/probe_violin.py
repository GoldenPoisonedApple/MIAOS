"""プローブ特徴のクラス別バイオリン図（シャドー IN/OUT・ターゲット共用）。

各クラスの分布を全画像 (n_models × K) の値で描き、平均を横線で示す。
検定対象のパネルには、Wilcoxon p 値の -log10 を下段に描き、
Bonferroni / BH-FDR の閾値線を引く。検定単位はパネルごとに
モデル単位 (K 枚平均) か画像単位 (K 枚) を選ぶ。
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.attacks.analysis.shadow_pair_effect_analysis import (
	bh_fdr_threshold_p,
	class_wilcoxon_pvalues,
	draw_neglog10_p_bar,
)

# 平均を示す横線のバイオリン幅に対する割合
_MEAN_LINE_HALF_WIDTH = 0.35


class SignificanceTest(Enum):
	"""下段に描く 0 に対するクラス別 Wilcoxon 検定の標本単位。"""

	# 検定しない（下段なし）
	NONE = "none"
	# モデル単位 (n_models 点, K 枚平均)。同一モデル内の K 枚は独立でないため、複数モデルではこちらを使う
	MODEL_LEVEL = "model_level"
	# 画像単位 (n_models × K 点)。1 モデルを固定した条件付き検定（単一ターゲット用）
	IMAGE_LEVEL = "image_level"


# 下段の y ラベルに付ける標本単位の注記
_TEST_UNIT_LABELS = {
	SignificanceTest.MODEL_LEVEL: "model-level (K-mean)",
	SignificanceTest.IMAGE_LEVEL: "image-level (K images)",
}


@dataclass(frozen=True)
class ProbeViolinPanel:
	"""バイオリン図 1 枚分の入力。

	values はモデルごとのプローブ特徴 (n_models, K, n_classes)。
	significance が NONE 以外のとき、値が 0 と異なるかをクラス別に検定する
	（差分パネルでは paired 検定、decorated - plain では 1 標本検定に相当）。
	"""

	name: str
	title: str
	ylabel: str
	values: np.ndarray
	significance: SignificanceTest = SignificanceTest.NONE

	def __post_init__(self) -> None:
		if self.values.ndim != 3:
			raise ValueError(
				f"values must be (n_models, K, n_classes), got ndim={self.values.ndim}"
			)

	@property
	def n_classes(self) -> int:
		return int(self.values.shape[2])

	@property
	def n_models(self) -> int:
		return int(self.values.shape[0])

	def per_image(self) -> np.ndarray:
		"""全画像の値 (n_models * K, n_classes)。"""
		return self.values.reshape(-1, self.n_classes)

	def per_model(self) -> np.ndarray:
		"""モデル単位の値 (n_models, n_classes)。K 枚平均。"""
		return self.values.mean(axis=1)

	def test_samples(self) -> np.ndarray:
		"""検定に使う標本 (n, n_classes)。significance に応じてモデル単位か画像単位。"""
		if self.significance is SignificanceTest.MODEL_LEVEL:
			return self.per_model()
		if self.significance is SignificanceTest.IMAGE_LEVEL:
			return self.per_image()
		raise ValueError(f"panel {self.name!r} has no significance test")


def _draw_class_violins(ax: plt.Axes, per_image: np.ndarray, ylabel: str) -> None:
	"""ax にクラス別バイオリンと平均の横線を描く。"""
	n_classes = per_image.shape[1]
	class_ids = np.arange(n_classes)
	means = per_image.mean(axis=0)

	parts = ax.violinplot(
		[per_image[:, c] for c in range(n_classes)],
		positions=class_ids,
		widths=0.8,
		showmeans=False,
		showextrema=False,
	)
	for body in parts["bodies"]:
		body.set_facecolor("lightgray")
		body.set_edgecolor("dimgray")
		body.set_linewidth(0.4)
		body.set_alpha(0.8)

	colors = np.where(means >= 0, "indianred", "steelblue")
	ax.hlines(
		means,
		class_ids - _MEAN_LINE_HALF_WIDTH,
		class_ids + _MEAN_LINE_HALF_WIDTH,
		colors=colors,
		linewidth=1.5,
		label="class mean",
	)
	ax.axhline(0.0, color="black", linewidth=0.5, linestyle=":")
	ax.set_xlim(-0.5, n_classes - 0.5)
	ax.set_xticks(class_ids[::10])
	ax.set_xticklabels([str(i) for i in class_ids[::10]])
	ax.set_xlabel("Class ID")
	ax.set_ylabel(ylabel)
	ax.legend(loc="upper right", fontsize=8)


def plot_class_violin(panel: ProbeViolinPanel, output_path: Path, alpha: float) -> None:
	"""1 パネル分のバイオリン図（検定対象なら -log10(p) の下段付き）を保存する。"""
	per_image = panel.per_image()
	n_models, k = panel.values.shape[:2]
	title = f"{panel.title} (all {panel.n_classes} classes, n_models={n_models}, K={k})"

	if panel.significance is SignificanceTest.NONE:
		fig, ax = plt.subplots(figsize=(16, 5))
		_draw_class_violins(ax, per_image, panel.ylabel)
		ax.set_title(title)
	else:
		fig, (ax_violin, ax_p) = plt.subplots(
			2, 1, figsize=(16, 8), sharex=True, gridspec_kw={"height_ratios": [3, 2]}
		)
		_draw_class_violins(ax_violin, per_image, panel.ylabel)
		ax_violin.set_title(title)
		ax_violin.set_xlabel("")

		samples = panel.test_samples()
		p_values = class_wilcoxon_pvalues(samples)
		draw_neglog10_p_bar(
			ax_p,
			samples.mean(axis=0),
			p_values,
			alpha,
			bh_fdr_threshold_p(p_values, alpha),
			ylabel=f"-log10(wilcoxon_p)\n{_TEST_UNIT_LABELS[panel.significance]}",
		)

	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def save_violin_panels(
	panels: list[ProbeViolinPanel],
	output_dir: str | Path,
	alpha: float = 0.05,
) -> Path:
	"""全パネルを {name}_violin.png として出力し、出力ディレクトリを返す。"""
	out_dir = Path(output_dir)
	out_dir.mkdir(parents=True, exist_ok=True)
	for panel in panels:
		plot_class_violin(panel, out_dir / f"{panel.name}_violin.png", alpha)
	return out_dir
