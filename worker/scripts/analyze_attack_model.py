"""AttackNet (LF_MIA 攻撃モデル) の重み解析・可視化 CLI。"""

import argparse
import glob
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

import src.core.config as cfg
from src.models.attack_model import AttackNet

# effective_path サマリに含める上位クラス数
EFFECTIVE_PATH_TOP_K = 10


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Analyze and visualize LF_MIA attack model weights."
	)
	parser.add_argument(
		"--attack-models",
		nargs="+",
		default=["scripts/results_*_attack_models.pth"],
		help="Path(s) to attack_models.pth (glob supported)",
	)
	parser.add_argument(
		"--output-dir",
		type=str,
		default="scripts/analysis_output",
		help="Directory to save PNG and JSON outputs",
	)
	return parser.parse_args()


def resolve_model_paths(patterns: list[str]) -> list[Path]:
	"""glob パターンを展開し、存在する .pth ファイルの一意なリストを返す。"""
	resolved: list[Path] = []
	seen: set[str] = set()
	for pattern in patterns:
		matches = sorted(glob.glob(pattern))
		if not matches and Path(pattern).is_file():
			matches = [pattern]
		if not matches:
			print(f"Warning: no files matched pattern: {pattern}", file=sys.stderr)
			continue
		for match in matches:
			path = Path(match).resolve()
			key = str(path)
			if key not in seen:
				seen.add(key)
				resolved.append(path)
	return resolved


def load_attack_model(path: Path) -> AttackNet | None:
	"""state_dict を読み込み AttackNet にロードする。失敗時は None。"""
	try:
		state_dict = torch.load(path, map_location="cpu", weights_only=True)
		model = AttackNet(input_dim=cfg.NUM_CLASSES)
		model.load_state_dict(state_dict)
		model.eval()
		return model
	except Exception as exc:
		print(f"Warning: failed to load {path}: {exc}", file=sys.stderr)
		return None


def compute_class_importance(w1: torch.Tensor) -> np.ndarray:
	"""第1層重み (out, in) からクラスごとの重要度を算出する。"""
	return w1.abs().sum(dim=0).cpu().numpy()


def compute_effective_path(w2: torch.Tensor, w1: torch.Tensor) -> np.ndarray:
	"""隠れ層を通した入力クラス→出力の合成係数 W2 @ W1 (2 x input_dim) を返す。

	ReLU・バイアスを無視した線形近似。C[out, class] はクラス確率が
	その出力ロジットを押し上げる方向の強度を表す。
	"""
	return (w2 @ w1).cpu().numpy()


def _top_class_entries(values: np.ndarray, top_k: int, descending: bool = True) -> list[dict]:
	"""クラス ID 順の配列から上位 top_k 件を {class_id, value} リストで返す。"""
	order = np.argsort(values)
	if descending:
		order = order[::-1]
	return [
		{"class_id": int(class_id), "value": float(values[class_id])}
		for class_id in order[:top_k]
	]


def summarize_effective_path(effective_path: np.ndarray, top_k: int = EFFECTIVE_PATH_TOP_K) -> dict:
	"""effective_path から IN/OUT 寄りの上位クラスを要約する。"""
	out_row = effective_path[0]
	in_row = effective_path[1]
	in_minus_out = in_row - out_row

	return {
		"note": "Linear approximation W2 @ W1 (ignores ReLU and bias)",
		"shape": [int(effective_path.shape[0]), int(effective_path.shape[1])],
		"top_in_classes": _top_class_entries(in_row, top_k),
		"top_out_classes": _top_class_entries(out_row, top_k),
		"top_in_leaning_classes": _top_class_entries(in_minus_out, top_k),
		"top_out_leaning_classes": _top_class_entries(-in_minus_out, top_k),
	}


def compute_summary(
	model: AttackNet,
	importance: np.ndarray,
	effective_path: np.ndarray,
) -> dict:
	w1 = model.net[0].weight.detach()
	w2 = model.net[2].weight.detach()
	b1 = model.net[0].bias.detach()
	b2 = model.net[2].bias.detach()

	return {
		"input_dim": cfg.NUM_CLASSES,
		"hidden_dim": int(w1.shape[0]),
		"weight_norms": {
			"net.0.weight": float(w1.norm().item()),
			"net.0.bias": float(b1.norm().item()),
			"net.2.weight": float(w2.norm().item()),
			"net.2.bias": float(b2.norm().item()),
		},
		"weight_stats": {
			"net.0.weight": {
				"mean": float(w1.mean().item()),
				"std": float(w1.std().item()),
				"min": float(w1.min().item()),
				"max": float(w1.max().item()),
			},
			"net.2.weight": {
				"mean": float(w2.mean().item()),
				"std": float(w2.std().item()),
				"min": float(w2.min().item()),
				"max": float(w2.max().item()),
			},
		},
		"class_importance": [float(v) for v in importance],
		"effective_path": summarize_effective_path(effective_path),
	}


def plot_weight_heatmap(w1: np.ndarray, output_path: Path) -> None:
	fig, ax = plt.subplots(figsize=(14, 6))
	im = ax.imshow(w1, aspect="auto", cmap="RdBu_r", interpolation="nearest")
	ax.set_xlabel("Class ID")
	ax.set_ylabel("Hidden unit")
	ax.set_title("First layer weights (64 x 100)")
	fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_class_importance(importance: np.ndarray, output_path: Path) -> None:
	"""クラス ID 順 (0..N-1) に全クラスの重要度を棒グラフで表示する。"""
	num_classes = len(importance)
	class_ids = np.arange(num_classes)

	fig, ax = plt.subplots(figsize=(16, 5))
	ax.bar(class_ids, importance, width=0.8, color="steelblue")
	ax.set_xlim(-0.5, num_classes - 0.5)
	ax.set_xticks(class_ids[::10])
	ax.set_xticklabels([str(i) for i in class_ids[::10]])
	ax.set_xlabel("Class ID")
	ax.set_ylabel("Importance (sum of |W1[:, j]|)")
	ax.set_title(f"Class importance (all {num_classes} classes, by class ID)")
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_output_layer_weights(w2: np.ndarray, output_path: Path) -> None:
	fig, ax = plt.subplots(figsize=(12, 3))
	im = ax.imshow(w2, aspect="auto", cmap="RdBu_r", interpolation="nearest")
	ax.set_yticks([0, 1])
	ax.set_yticklabels(["OUT (0)", "IN (1)"])
	ax.set_xlabel("Hidden unit")
	ax.set_title("Output layer weights (2 x 64)")
	fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_effective_path_heatmap(effective_path: np.ndarray, output_path: Path) -> None:
	"""W2 @ W1 の合成係数 (2 x num_classes) をヒートマップ表示する。"""
	num_classes = effective_path.shape[1]
	fig, ax = plt.subplots(figsize=(14, 3))
	im = ax.imshow(effective_path, aspect="auto", cmap="RdBu_r", interpolation="nearest")
	ax.set_yticks([0, 1])
	ax.set_yticklabels(["OUT (0)", "IN (1)"])
	ax.set_xlabel("Class ID")
	ax.set_title(
		f"Effective path W2 @ W1 ({effective_path.shape[0]} x {num_classes}, linear approx.)"
	)
	fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def analyze_model(path: Path, output_dir: Path) -> bool:
	label = path.stem.removesuffix("_attack_models")
	model_dir = output_dir / label
	model_dir.mkdir(parents=True, exist_ok=True)

	model = load_attack_model(path)
	if model is None:
		return False

	w1_tensor = model.net[0].weight.detach()
	w2_tensor = model.net[2].weight.detach()
	w1 = w1_tensor.cpu().numpy()
	w2 = w2_tensor.cpu().numpy()
	importance = compute_class_importance(w1_tensor)
	effective_path = compute_effective_path(w2_tensor, w1_tensor)

	summary = compute_summary(model, importance, effective_path)
	summary["source_file"] = str(path)

	plot_weight_heatmap(w1, model_dir / "weight_heatmap.png")
	plot_class_importance(importance, model_dir / "class_importance.png")
	plot_output_layer_weights(w2, model_dir / "output_layer_weights.png")
	plot_effective_path_heatmap(effective_path, model_dir / "effective_path_heatmap.png")

	with open(model_dir / "summary.json", "w", encoding="utf-8") as f:
		json.dump(summary, f, indent=2, ensure_ascii=False)

	print(f"Analyzed: {path.name} -> {model_dir}")
	return True


def main() -> None:
	args = parse_args()
	model_paths = resolve_model_paths(args.attack_models)
	if not model_paths:
		print("Error: no attack model files found.", file=sys.stderr)
		sys.exit(1)

	output_dir = Path(args.output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	success_count = 0
	for path in model_paths:
		if analyze_model(path, output_dir):
			success_count += 1

	print(f"Done: {success_count}/{len(model_paths)} model(s) analyzed -> {output_dir}")
	if success_count == 0:
		sys.exit(1)


if __name__ == "__main__":
	main()
