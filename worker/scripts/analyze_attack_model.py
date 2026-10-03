"""AttackNet (LF_MIA 攻撃モデル) の重み解析・可視化 CLI。

学習済み重みの絶対値だけでは初期化ノイズと学習成分を区別できないため、
初期重み (ベースライン) との差分 ``W_trained - W_init`` も併せて可視化する。
ベースラインは ``--init-state-dict`` (保存済み初期重み) か ``--init-seed``
(同一 seed から再生成) で与える。どちらも無い場合は差分を計算せず、
未学習モデル 1 本を参照用に解析して並べる。
"""

import argparse
import glob
import json
import sys
from dataclasses import dataclass
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
# 「seed から再生成した初期重み」が本当に学習前の重みと一致しているかを判定する
# 相関係数の下限。これ未満なら seed が一致していないとみなし警告を出す。
INIT_MATCH_MIN_CORRELATION = 0.5
# ベースライン未指定時に参照用の未学習モデルを生成する seed
UNTRAINED_REFERENCE_SEED = 0
# 参照用の未学習モデルの出力ディレクトリ名
UNTRAINED_REFERENCE_DIR_NAME = "untrained_reference"


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
	parser.add_argument(
		"--init-state-dict",
		type=str,
		default=None,
		help=(
			"Path to the attack model's *initial* state_dict (before training). "
			"Used as the baseline for delta (W_trained - W_init) plots."
		),
	)
	parser.add_argument(
		"--init-seed",
		nargs="+",
		type=int,
		default=None,
		help=(
			"Candidate seed(s) to regenerate the initial weights via torch.manual_seed. "
			"The seed whose W1 correlates best with the trained W1 is used as baseline. "
			"Ignored when --init-state-dict is given."
		),
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


def build_untrained_model(seed: int) -> AttackNet:
	"""指定 seed で RNG を固定し、未学習の AttackNet を生成する。

	lf_mia.py と同じく CPU 上で生成するため、nn.Linear の初期化は
	CPU 側の RNG のみに依存する。
	"""
	torch.manual_seed(seed)
	model = AttackNet(input_dim=cfg.NUM_CLASSES)
	model.eval()
	return model


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
# ベースライン (初期重み) の解決
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InitBaseline:
	"""差分計算に用いる初期重みと、その出所・妥当性の情報。"""

	snapshot: WeightSnapshot
	source: str  # "state_dict" | "seed"
	seed: int | None
	# 学習済み W1 と初期 W1 の Pearson 相関。seed 由来のベースラインが
	# 本当に学習前の重みと一致しているかの指標 (一致なら 1 に近い)。
	w1_correlation: float

	@property
	def is_reliable(self) -> bool:
		return self.w1_correlation >= INIT_MATCH_MIN_CORRELATION


def compute_w1_correlation(trained: WeightSnapshot, init: WeightSnapshot) -> float:
	"""学習済み W1 と初期 W1 を平坦化して Pearson 相関を計算する。"""
	a = trained.w1.ravel()
	b = init.w1.ravel()
	if a.std() == 0.0 or b.std() == 0.0:
		return 0.0
	return float(np.corrcoef(a, b)[0, 1])


def resolve_init_baseline(
	trained: WeightSnapshot,
	init_state_dict: str | None,
	init_seeds: list[int] | None,
) -> InitBaseline | None:
	"""CLI 引数からベースラインを決定する。

	優先順位: --init-state-dict > --init-seed (複数なら相関最大の seed) > None。
	"""
	if init_state_dict is not None:
		model = load_attack_model(Path(init_state_dict))
		if model is None:
			return None
		snapshot = WeightSnapshot.from_model(model)
		return InitBaseline(
			snapshot=snapshot,
			source="state_dict",
			seed=None,
			w1_correlation=compute_w1_correlation(trained, snapshot),
		)

	if init_seeds:
		best: InitBaseline | None = None
		for seed in init_seeds:
			snapshot = WeightSnapshot.from_model(build_untrained_model(seed))
			candidate = InitBaseline(
				snapshot=snapshot,
				source="seed",
				seed=seed,
				w1_correlation=compute_w1_correlation(trained, snapshot),
			)
			if best is None or candidate.w1_correlation > best.w1_correlation:
				best = candidate
		return best

	return None


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


def compute_delta_summary(baseline: InitBaseline, delta: WeightDelta) -> dict:
	"""初期重みとの差分に関するサマリ。学習成分のみを表す。"""
	w1_init_norm = float(np.linalg.norm(baseline.snapshot.w1))
	w1_delta_norm = float(np.linalg.norm(delta.w1))
	return {
		"source": baseline.source,
		"seed": baseline.seed,
		"w1_correlation_with_trained": baseline.w1_correlation,
		"is_reliable": baseline.is_reliable,
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


def analyze_model(
	path: Path,
	output_dir: Path,
	init_state_dict: str | None,
	init_seeds: list[int] | None,
) -> bool:
	label = path.stem.removesuffix("_attack_models")
	model_dir = output_dir / label
	model_dir.mkdir(parents=True, exist_ok=True)

	model = load_attack_model(path)
	if model is None:
		return False

	trained = WeightSnapshot.from_model(model)
	summary = compute_summary(trained)
	summary["source_file"] = str(path)

	plot_snapshot(trained, model_dir)

	baseline = resolve_init_baseline(trained, init_state_dict, init_seeds)
	if baseline is None:
		summary["init_baseline"] = None
	else:
		if not baseline.is_reliable:
			print(
				f"Warning: {path.name}: init baseline (source={baseline.source}, seed={baseline.seed}) "
				f"has low W1 correlation {baseline.w1_correlation:.3f} < {INIT_MATCH_MIN_CORRELATION}. "
				"The seed likely does not reproduce the actual initial weights; "
				"delta plots are not meaningful.",
				file=sys.stderr,
			)
		delta = WeightDelta.between(trained, baseline.snapshot)
		summary["init_baseline"] = compute_delta_summary(baseline, delta)
		plot_delta(delta, model_dir)

	with open(model_dir / "summary.json", "w", encoding="utf-8") as f:
		json.dump(summary, f, indent=2, ensure_ascii=False)

	print(f"Analyzed: {path.name} -> {model_dir}")
	return True


def write_untrained_reference(output_dir: Path, seed: int) -> None:
	"""ベースライン未指定時に、未学習モデル 1 本を参照用に解析して出力する。

	学習済みモデルの図がこれと見分けがつかないなら、重みは初期化から
	ほとんど動いていないと判断できる。
	"""
	ref_dir = output_dir / UNTRAINED_REFERENCE_DIR_NAME
	ref_dir.mkdir(parents=True, exist_ok=True)

	snapshot = WeightSnapshot.from_model(build_untrained_model(seed))
	summary = compute_summary(snapshot)
	summary["source_file"] = None
	summary["note"] = (
		f"Untrained AttackNet generated with torch.manual_seed({seed}) "
		"for visual comparison. Not the actual initial weights of any trained model."
	)

	plot_snapshot(snapshot, ref_dir, label_prefix="[untrained reference] ")

	with open(ref_dir / "summary.json", "w", encoding="utf-8") as f:
		json.dump(summary, f, indent=2, ensure_ascii=False)

	print(f"Untrained reference (seed={seed}) -> {ref_dir}")


def main() -> None:
	args = parse_args()
	model_paths = resolve_model_paths(args.attack_models)
	if not model_paths:
		print("Error: no attack model files found.", file=sys.stderr)
		sys.exit(1)

	output_dir = Path(args.output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	if args.init_state_dict is None and not args.init_seed:
		print(
			"Note: neither --init-state-dict nor --init-seed given; "
			"delta plots are skipped and an untrained reference model is written instead.",
			file=sys.stderr,
		)
		write_untrained_reference(output_dir, UNTRAINED_REFERENCE_SEED)

	success_count = 0
	for path in model_paths:
		if analyze_model(path, output_dir, args.init_state_dict, args.init_seed):
			success_count += 1

	print(f"Done: {success_count}/{len(model_paths)} model(s) analyzed -> {output_dir}")
	if success_count == 0:
		sys.exit(1)


if __name__ == "__main__":
	main()
