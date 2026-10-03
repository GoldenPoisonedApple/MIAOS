"""AttackNet (LF_MIA 攻撃モデル) の重み解析・可視化。

学習済み重みの絶対値だけでは初期化ノイズと学習成分を区別できないため、
初期重み (ベースライン) との差分 ``W_trained - W_init`` も併せて可視化する。
"""

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.models.attack_model import AttackNet

# effective_path サマリに含める上位クラス数
EFFECTIVE_PATH_TOP_K = 10


# ---------------------------------------------------------------------------
# 重みのスナップショットと派生量
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeightSnapshot:
	"""AttackNet の全パラメータを numpy で保持する不変オブジェクト。

	学習済み・初期化のみ・両者の差分を同じ型で扱えるようにし、
	可視化・サマリ生成のコードを共通化する。
	"""

	w1: np.ndarray  # (hidden, input)
	b1: np.ndarray  # (hidden,)
	w2: np.ndarray  # (2, hidden)
	b2: np.ndarray  # (2,)

	@classmethod
	def from_model(cls, model: AttackNet) -> "WeightSnapshot":
		return cls(
			w1=model.net[0].weight.detach().cpu().numpy(),
			b1=model.net[0].bias.detach().cpu().numpy(),
			w2=model.net[2].weight.detach().cpu().numpy(),
			b2=model.net[2].bias.detach().cpu().numpy(),
		)

	@property
	def hidden_dim(self) -> int:
		return int(self.w1.shape[0])

	@property
	def input_dim(self) -> int:
		return int(self.w1.shape[1])

	def class_importance(self) -> np.ndarray:
		"""第1層重み (out, in) からクラスごとの重要度 sum_j |W1[j, c]| を算出する。"""
		return np.abs(self.w1).sum(axis=0)

	def effective_path(self) -> np.ndarray:
		"""隠れ層を通した入力クラス→出力の合成係数 W2 @ W1 (2 x input_dim) を返す。

		ReLU・バイアスを無視した線形近似。C[out, class] はクラス確率が
		その出力ロジットを押し上げる方向の強度を表す。
		"""
		return self.w2 @ self.w1


@dataclass(frozen=True)
class WeightDelta:
	"""学習済み重みと初期重みの差分。

	effective_path は ``(W2 @ W1)_trained - (W2 @ W1)_init`` であり、
	``ΔW2 @ ΔW1`` ではない点に注意 (後者は交差項を落としてしまう)。
	"""

	w1: np.ndarray
	b1: np.ndarray
	w2: np.ndarray
	b2: np.ndarray
	effective_path: np.ndarray

	@classmethod
	def between(cls, trained: WeightSnapshot, init: WeightSnapshot) -> "WeightDelta":
		return cls(
			w1=trained.w1 - init.w1,
			b1=trained.b1 - init.b1,
			w2=trained.w2 - init.w2,
			b2=trained.b2 - init.b2,
			effective_path=trained.effective_path() - init.effective_path(),
		)

	def class_importance(self) -> np.ndarray:
		"""学習で動いた量のクラス別合計 sum_j |ΔW1[j, c]|。"""
		return np.abs(self.w1).sum(axis=0)


# ---------------------------------------------------------------------------
# サマリ生成
# ---------------------------------------------------------------------------


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


def _array_stats(values: np.ndarray) -> dict:
	return {
		"mean": float(values.mean()),
		"std": float(values.std()),
		"min": float(values.min()),
		"max": float(values.max()),
	}


def _weight_norms(w1: np.ndarray, b1: np.ndarray, w2: np.ndarray, b2: np.ndarray) -> dict:
	return {
		"net.0.weight": float(np.linalg.norm(w1)),
		"net.0.bias": float(np.linalg.norm(b1)),
		"net.2.weight": float(np.linalg.norm(w2)),
		"net.2.bias": float(np.linalg.norm(b2)),
	}


def compute_summary(snapshot: WeightSnapshot) -> dict:
	return {
		"input_dim": snapshot.input_dim,
		"hidden_dim": snapshot.hidden_dim,
		"weight_norms": _weight_norms(snapshot.w1, snapshot.b1, snapshot.w2, snapshot.b2),
		"weight_stats": {
			"net.0.weight": _array_stats(snapshot.w1),
			"net.2.weight": _array_stats(snapshot.w2),
		},
		"class_importance": [float(v) for v in snapshot.class_importance()],
		"effective_path": summarize_effective_path(snapshot.effective_path()),
	}


def compute_delta_summary(init: WeightSnapshot, delta: WeightDelta) -> dict:
	"""初期重みとの差分に関するサマリ。学習成分のみを表す。"""
	w1_init_norm = float(np.linalg.norm(init.w1))
	w1_delta_norm = float(np.linalg.norm(delta.w1))
	return {
		"note": (
			"delta = trained - init. effective_path delta is "
			"(W2@W1)_trained - (W2@W1)_init, not dW2@dW1."
		),
		"delta_norms": _weight_norms(delta.w1, delta.b1, delta.w2, delta.b2),
		# 学習で動いた量 / 初期重みの大きさ。1 を大きく下回るなら学習成分は初期化ノイズに埋もれている。
		"w1_relative_change": (w1_delta_norm / w1_init_norm) if w1_init_norm > 0 else None,
		"delta_stats": {
			"net.0.weight": _array_stats(delta.w1),
			"net.2.weight": _array_stats(delta.w2),
		},
		"delta_class_importance": [float(v) for v in delta.class_importance()],
		"delta_effective_path": summarize_effective_path(delta.effective_path),
	}


# ---------------------------------------------------------------------------
# 可視化
# ---------------------------------------------------------------------------


def _symmetric_vlim(values: np.ndarray) -> float:
	"""0 を中心とした対称カラースケールの絶対値上限を返す。"""
	vmax = float(np.abs(values).max())
	return vmax if vmax > 0 else 1.0


def plot_weight_heatmap(w1: np.ndarray, output_path: Path, title: str) -> None:
	vlim = _symmetric_vlim(w1)
	fig, ax = plt.subplots(figsize=(14, 6))
	im = ax.imshow(
		w1, aspect="auto", cmap="RdBu_r", interpolation="nearest", vmin=-vlim, vmax=vlim
	)
	ax.set_xlabel("Class ID")
	ax.set_ylabel("Hidden unit")
	ax.set_title(title)
	fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_class_importance(
	importance: np.ndarray, output_path: Path, title: str, ylabel: str
) -> None:
	"""クラス ID 順 (0..N-1) に全クラスの重要度を棒グラフで表示する。"""
	num_classes = len(importance)
	class_ids = np.arange(num_classes)

	fig, ax = plt.subplots(figsize=(16, 5))
	ax.bar(class_ids, importance, width=0.8, color="steelblue")
	ax.set_xlim(-0.5, num_classes - 0.5)
	ax.set_xticks(class_ids[::10])
	ax.set_xticklabels([str(i) for i in class_ids[::10]])
	ax.set_xlabel("Class ID")
	ax.set_ylabel(ylabel)
	ax.set_title(title)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_output_layer_weights(w2: np.ndarray, output_path: Path, title: str) -> None:
	vlim = _symmetric_vlim(w2)
	fig, ax = plt.subplots(figsize=(12, 3))
	im = ax.imshow(
		w2, aspect="auto", cmap="RdBu_r", interpolation="nearest", vmin=-vlim, vmax=vlim
	)
	ax.set_yticks([0, 1])
	ax.set_yticklabels(["OUT (0)", "IN (1)"])
	ax.set_xlabel("Hidden unit")
	ax.set_title(title)
	fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_effective_path_heatmap(effective_path: np.ndarray, output_path: Path, title: str) -> None:
	"""W2 @ W1 の合成係数 (2 x num_classes) をヒートマップ表示する。"""
	vlim = _symmetric_vlim(effective_path)
	fig, ax = plt.subplots(figsize=(14, 3))
	im = ax.imshow(
		effective_path,
		aspect="auto",
		cmap="RdBu_r",
		interpolation="nearest",
		vmin=-vlim,
		vmax=vlim,
	)
	ax.set_yticks([0, 1])
	ax.set_yticklabels(["OUT (0)", "IN (1)"])
	ax.set_xlabel("Class ID")
	ax.set_title(title)
	fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_snapshot(snapshot: WeightSnapshot, model_dir: Path, label_prefix: str = "") -> None:
	"""学習済み / 未学習モデルの絶対値ベースの 4 図を出力する。"""
	hidden, inputs = snapshot.hidden_dim, snapshot.input_dim
	plot_weight_heatmap(
		snapshot.w1,
		model_dir / "weight_heatmap.png",
		f"{label_prefix}First layer weights ({hidden} x {inputs})",
	)
	plot_class_importance(
		snapshot.class_importance(),
		model_dir / "class_importance.png",
		f"{label_prefix}Class importance (all {inputs} classes, by class ID)",
		"Importance (sum of |W1[:, j]|)",
	)
	plot_output_layer_weights(
		snapshot.w2,
		model_dir / "output_layer_weights.png",
		f"{label_prefix}Output layer weights (2 x {hidden})",
	)
	plot_effective_path_heatmap(
		snapshot.effective_path(),
		model_dir / "effective_path_heatmap.png",
		f"{label_prefix}Effective path W2 @ W1 (2 x {inputs}, linear approx.)",
	)


def plot_delta(delta: WeightDelta, model_dir: Path) -> None:
	"""初期重みとの差分 (学習成分のみ) の 4 図を delta_*.png として出力する。"""
	hidden, inputs = delta.w1.shape
	plot_weight_heatmap(
		delta.w1,
		model_dir / "delta_weight_heatmap.png",
		f"First layer weight delta W1_trained - W1_init ({hidden} x {inputs})",
	)
	plot_class_importance(
		delta.class_importance(),
		model_dir / "delta_class_importance.png",
		f"Class importance of learned delta (all {inputs} classes, by class ID)",
		"Learned change (sum of |dW1[:, j]|)",
	)
	plot_output_layer_weights(
		delta.w2,
		model_dir / "delta_output_layer_weights.png",
		f"Output layer weight delta W2_trained - W2_init (2 x {hidden})",
	)
	plot_effective_path_heatmap(
		delta.effective_path,
		model_dir / "delta_effective_path_heatmap.png",
		f"Effective path delta (W2@W1)_trained - (W2@W1)_init (2 x {inputs}, linear approx.)",
	)


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------


def analyze_attack_model(
	trained_model: AttackNet,
	output_dir: str | Path,
	init_model: AttackNet,
) -> float | None:
	"""学習済み AttackNet の重みを解析し、PNG と summary.json を出力する。

	Args:
		trained_model: 学習後の AttackNet
		output_dir: 出力ディレクトリ（存在しなければ作成）
		init_model: 訓練前の AttackNet（初期重みのベースライン）

	Returns:
		w1_relative_change: 第1層重みの学習による相対変化量
	"""
	model_dir = Path(output_dir)
	model_dir.mkdir(parents=True, exist_ok=True)

	trained = WeightSnapshot.from_model(trained_model)
	init = WeightSnapshot.from_model(init_model)
	summary = compute_summary(trained)

	plot_snapshot(trained, model_dir)

	delta = WeightDelta.between(trained, init)
	delta_summary = compute_delta_summary(init, delta)
	summary["delta"] = delta_summary
	plot_delta(delta, model_dir)

	summary_path = model_dir / "summary.json"
	with open(summary_path, "w", encoding="utf-8") as f:
		json.dump(summary, f, indent=2, ensure_ascii=False)

	return delta_summary["w1_relative_change"]
