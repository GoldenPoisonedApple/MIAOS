"""LF_MIA 系ターゲットモデルへの攻撃透かし入力時のクラス別確率出力の可視化。

各ターゲットモデル（装飾適用率 13 段階）に攻撃用透かしを入力し、
softmax 確率を棒グラフとして ``target_attacksign_output/`` に出力する。
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.attacks.attack_model_analysis import plot_class_importance

# summary.json に含める上位クラス数
TOP_K_CLASSES = 10


@dataclass(frozen=True)
class TargetAttackSignEntry:
	"""1 ターゲットモデル分の攻撃透かし出力。"""

	fraction: float
	# クラス別 softmax 確率 (num_classes,)
	probs: np.ndarray


def _fraction_to_filename(fraction: float) -> str:
	"""fraction をファイル名安全な文字列に変換する (例: 0.001 -> 0_001, 1.0 -> 1_0)。"""
	return str(fraction).replace(".", "_")


def _top_class_entries(values: np.ndarray, top_k: int = TOP_K_CLASSES) -> list[dict]:
	"""確率値の上位 top_k クラスを {class_id, value} リストで返す。"""
	order = np.argsort(values)[::-1]
	return [
		{"class_id": int(class_id), "value": float(values[class_id])}
		for class_id in order[:top_k]
	]


def plot_class_probabilities(
	values: np.ndarray, output_path: Path, title: str, ylabel: str = "Probability"
) -> None:
	"""クラス別 softmax 確率の棒グラフを出力する。"""
	plot_class_importance(values, output_path, title, ylabel)


def analyze_target_attack_sign_output(
	entries: list[TargetAttackSignEntry],
	output_dir: str | Path,
) -> Path:
	"""ターゲットモデル群の攻撃透かし確率出力を PNG と summary.json に保存する。

	Args:
		entries: 各ターゲットモデル（fraction ごと）の確率出力
		output_dir: 出力ディレクトリ（存在しなければ作成）

	Returns:
		summary.json のパス
	"""
	model_dir = Path(output_dir)
	model_dir.mkdir(parents=True, exist_ok=True)

	summary_entries: list[dict] = []
	for entry in entries:
		fraction_label = _fraction_to_filename(entry.fraction)
		title_suffix = f"fraction={entry.fraction}"

		plot_path = model_dir / f"class_probabilities_fraction_{fraction_label}.png"
		plot_class_probabilities(
			entry.probs,
			plot_path,
			f"Probability on attack watermark ({title_suffix})",
		)

		entry_summary: dict = {
			"fraction": entry.fraction,
			"probs": [float(v) for v in entry.probs],
			"argmax_class": int(np.argmax(entry.probs)),
			"argmax_value": float(entry.probs[np.argmax(entry.probs)]),
			"top_classes": _top_class_entries(entry.probs),
			"plot_path": plot_path.name,
		}
		summary_entries.append(entry_summary)

	summary = {"entries": summary_entries}
	summary_path = model_dir / "summary.json"
	with open(summary_path, "w", encoding="utf-8") as f:
		json.dump(summary, f, indent=2, ensure_ascii=False)

	return summary_path
