"""AttackNet (LF_MIA 攻撃モデル) の重み解析・可視化。

学習済み重みの絶対値だけでは初期化ノイズと学習成分を区別できないため、
初期重み (ベースライン) との差分 ``W_trained - W_init`` も併せて可視化する。

さらに、重みだけでは入力スケール (クラスごとに桁が異なる logit 特徴) と
ReLU の活性状態を考慮できないため、攻撃モデルの学習データ ``attack_x`` /
``attack_y`` を用いたデータ駆動の解析 (学習到達度・入力勾配・活性マスク込みの
実効パス) も併せて出力する。
"""

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as F

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


def summarize_effective_path(
	effective_path: np.ndarray,
	top_k: int = EFFECTIVE_PATH_TOP_K,
	note: str = "Linear approximation W2 @ W1 (ignores ReLU and bias)",
) -> dict:
	"""effective_path から IN/OUT 寄りの上位クラスを要約する。

	softmax はロジットの共通シフトに不変なので、IN 行・OUT 行を個別に見ても
	意味がない。判定に効くのは差 ``IN - OUT`` のみなので、その上位・下位だけを出す。
	"""
	out_row = effective_path[0]
	in_row = effective_path[1]
	in_minus_out = in_row - out_row

	return {
		"note": note,
		"shape": [int(effective_path.shape[0]), int(effective_path.shape[1])],
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
# 学習データ (attack_x, attack_y) を用いたデータ駆動の解析
# ---------------------------------------------------------------------------


def _model_device(model: AttackNet) -> torch.device:
	return next(model.parameters()).device


@dataclass(frozen=True)
class FitMetrics:
	"""攻撃モデルの学習データ上での到達度。

	攻撃モデルが IN/OUT を分離できていなければ重み解析自体に意味がないため、
	重み解析の前提条件として記録する。
	"""

	num_samples: int
	num_in: int
	num_out: int
	accuracy: float
	loss: float  # 平均 cross entropy
	in_accuracy: float | None  # IN サンプルが 0 件なら None
	out_accuracy: float | None  # OUT サンプルが 0 件なら None

	def to_dict(self) -> dict:
		return {
			"num_samples": self.num_samples,
			"num_in": self.num_in,
			"num_out": self.num_out,
			"accuracy": self.accuracy,
			"loss": self.loss,
			"in_accuracy": self.in_accuracy,
			"out_accuracy": self.out_accuracy,
		}


def compute_fit_metrics(model: AttackNet, x: torch.Tensor, y: torch.Tensor) -> FitMetrics:
	"""学習データ上の精度・損失を計算する (学習時と同じ cross entropy)。"""
	model.eval()
	device = _model_device(model)
	with torch.no_grad():
		logits = model(x.to(device))
		y_dev = y.to(device)
		loss = float(F.cross_entropy(logits, y_dev).item())
		correct = logits.argmax(dim=1) == y_dev
		in_mask = y_dev == 1
		out_mask = y_dev == 0
		num_in = int(in_mask.sum().item())
		num_out = int(out_mask.sum().item())
	return FitMetrics(
		num_samples=int(y.numel()),
		num_in=num_in,
		num_out=num_out,
		accuracy=float(correct.float().mean().item()),
		loss=loss,
		in_accuracy=float(correct[in_mask].float().mean().item()) if num_in > 0 else None,
		out_accuracy=float(correct[out_mask].float().mean().item()) if num_out > 0 else None,
	)


@dataclass(frozen=True)
class InputSensitivity:
	"""攻撃モデルの入力感度 (学習データ ``attack_x`` 上で評価)。

	``margin = logit_IN - logit_OUT`` の入力勾配 ``∂margin/∂x`` を各サンプルで求める。
	AttackNet は ReLU の区分線形ネットワークなので、サンプル n の勾配は
	活性マスク m_n を使った ``(W2 diag(m_n) W1)[IN] - (W2 diag(m_n) W1)[OUT]`` に厳密一致する。
	したがって ``signed_mean_gradient`` は ``activation_aware_effective_path`` の
	IN 行 - OUT 行と同値であり、``W2 @ W1`` の線形近似を ReLU 込みに補正したものになる。

	重みの絶対値 (class_importance) は入力スケールを無視するため、
	クラスごとの入力標準偏差を掛けた ``scaled_importance`` を実効的な寄与の指標とする。
	"""

	signed_mean_gradient: np.ndarray  # (C,) 正なら IN 方向、負なら OUT 方向
	mean_abs_gradient: np.ndarray  # (C,) 符号を無視したサンプル平均感度
	input_std: np.ndarray  # (C,) attack_x のクラス別標準偏差
	hidden_activation_rate: np.ndarray  # (hidden,) 各隠れユニットが ReLU を通過した割合
	activation_aware_effective_path: np.ndarray  # (2, C) = W2 diag(mean m) W1

	@property
	def scaled_importance(self) -> np.ndarray:
		"""入力スケールを考慮した実効寄与 mean|∂margin/∂x_c| * std(x_c)。"""
		return self.mean_abs_gradient * self.input_std

	@property
	def dead_hidden_units(self) -> int:
		"""全サンプルで非活性だった隠れユニット数 (出力に一切寄与しない)。"""
		return int(np.sum(self.hidden_activation_rate == 0.0))

	@property
	def always_active_hidden_units(self) -> int:
		"""全サンプルで活性だった隠れユニット数 (そのユニットは純粋に線形)。"""
		return int(np.sum(self.hidden_activation_rate == 1.0))


def compute_input_sensitivity(model: AttackNet, x: torch.Tensor) -> InputSensitivity:
	"""attack_x 上で入力勾配・活性率・活性マスク込み実効パスを計算する。"""
	model.eval()
	device = _model_device(model)
	x_dev = x.to(device).detach().float().requires_grad_(True)

	# forward を層ごとに分解し、ReLU 前の値から活性マスクを取得する
	hidden_pre = model.net[0](x_dev)
	logits = model.net[2](torch.relu(hidden_pre))
	margin = logits[:, 1] - logits[:, 0]
	# 各サンプルの margin は自身の入力にしか依存しないので、総和の勾配 = サンプルごとの勾配
	(grad,) = torch.autograd.grad(margin.sum(), x_dev)

	mask = (hidden_pre > 0).float()
	mean_mask = mask.mean(dim=0)  # (hidden,)
	w1 = model.net[0].weight.detach()
	w2 = model.net[2].weight.detach()
	# mean_n [W2 diag(m_n) W1] = W2 diag(mean_n m_n) W1 (マスクに対して線形)
	activation_aware_path = (w2 * mean_mask[None, :]) @ w1

	return InputSensitivity(
		signed_mean_gradient=grad.mean(dim=0).cpu().numpy(),
		mean_abs_gradient=grad.abs().mean(dim=0).cpu().numpy(),
		# N=1 でも NaN にならないよう母標準偏差を使う
		input_std=x.detach().float().std(dim=0, unbiased=False).cpu().numpy(),
		hidden_activation_rate=mean_mask.cpu().numpy(),
		activation_aware_effective_path=activation_aware_path.cpu().numpy(),
	)


def summarize_input_sensitivity(
	sensitivity: InputSensitivity,
	linear_effective_path: np.ndarray,
	top_k: int = EFFECTIVE_PATH_TOP_K,
) -> dict:
	"""入力感度の要約。線形近似 W2 @ W1 との乖離も併記する。"""
	linear_norm = float(np.linalg.norm(linear_effective_path))
	gap = float(np.linalg.norm(linear_effective_path - sensitivity.activation_aware_effective_path))
	return {
		"note": (
			"Evaluated on attack_x. signed_mean_gradient = mean_n d(logit_IN - logit_OUT)/dx, "
			"which equals IN - OUT row of activation_aware_effective_path (exact for ReLU nets). "
			"scaled_importance = mean|grad| * std(x_c) accounts for per-class input scale."
		),
		"signed_mean_gradient": [float(v) for v in sensitivity.signed_mean_gradient],
		"mean_abs_gradient": [float(v) for v in sensitivity.mean_abs_gradient],
		"input_std": [float(v) for v in sensitivity.input_std],
		"scaled_importance": [float(v) for v in sensitivity.scaled_importance],
		"top_in_leaning_classes": _top_class_entries(sensitivity.signed_mean_gradient, top_k),
		"top_out_leaning_classes": _top_class_entries(-sensitivity.signed_mean_gradient, top_k),
		"top_scaled_importance_classes": _top_class_entries(sensitivity.scaled_importance, top_k),
		"hidden_activation_rate": [float(v) for v in sensitivity.hidden_activation_rate],
		"dead_hidden_units": sensitivity.dead_hidden_units,
		"always_active_hidden_units": sensitivity.always_active_hidden_units,
		"activation_aware_effective_path": summarize_effective_path(
			sensitivity.activation_aware_effective_path,
			top_k,
			note="W2 diag(mean ReLU mask) W1 evaluated on attack_x (ignores bias)",
		),
		# 線形近似 W2 @ W1 と活性マスク込み実効パスの相対乖離。大きいほど線形近似は信頼できない。
		"linear_approx_relative_gap": (gap / linear_norm) if linear_norm > 0 else None,
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


def plot_signed_class_values(
	values: np.ndarray, output_path: Path, title: str, ylabel: str
) -> None:
	"""符号付きのクラス別値を棒グラフ表示する (正: IN 方向=赤, 負: OUT 方向=青)。"""
	num_classes = len(values)
	class_ids = np.arange(num_classes)
	colors = np.where(values >= 0, "indianred", "steelblue")

	fig, ax = plt.subplots(figsize=(16, 5))
	ax.bar(class_ids, values, width=0.8, color=colors)
	ax.axhline(0.0, color="black", linewidth=0.8)
	ax.set_xlim(-0.5, num_classes - 0.5)
	ax.set_xticks(class_ids[::10])
	ax.set_xticklabels([str(i) for i in class_ids[::10]])
	ax.set_xlabel("Class ID")
	ax.set_ylabel(ylabel)
	ax.set_title(title)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def plot_input_sensitivity(sensitivity: InputSensitivity, model_dir: Path) -> None:
	"""attack_x 上の入力感度に関する 3 図を出力する。"""
	inputs = len(sensitivity.signed_mean_gradient)
	plot_signed_class_values(
		sensitivity.signed_mean_gradient,
		model_dir / "input_gradient_signed.png",
		f"Mean input gradient of (logit_IN - logit_OUT) on attack_x (all {inputs} classes)",
		"mean d(margin)/dx_c (+: IN, -: OUT)",
	)
	plot_class_importance(
		sensitivity.scaled_importance,
		model_dir / "input_gradient_scaled_importance.png",
		f"Scale-aware importance mean|d(margin)/dx_c| * std(x_c) (all {inputs} classes)",
		"mean|grad| * std(x_c)",
	)
	plot_effective_path_heatmap(
		sensitivity.activation_aware_effective_path,
		model_dir / "activation_effective_path_heatmap.png",
		f"Activation-aware effective path W2 diag(mean ReLU mask) W1 (2 x {inputs})",
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


@dataclass(frozen=True)
class AttackModelAnalysisResult:
	"""解析結果のうち、呼び出し側が metrics に載せる値をまとめた値オブジェクト。

	ファイル出力の詳細 (summary.json / PNG) は ``summary_path`` 配下を参照する。
	"""

	# 第1層重みの学習による相対変化量 ||ΔW1|| / ||W1_init||
	w1_relative_change: float | None
	# 攻撃モデルの学習データ上での到達度
	fit: FitMetrics
	summary_path: Path


def analyze_attack_model(
	trained_model: AttackNet,
	output_dir: str | Path,
	init_model: AttackNet,
	attack_x: torch.Tensor,
	attack_y: torch.Tensor,
) -> AttackModelAnalysisResult:
	"""学習済み AttackNet を解析し、PNG と summary.json を出力する。

	Args:
		trained_model: 学習後の AttackNet
		output_dir: 出力ディレクトリ（存在しなければ作成）
		init_model: 訓練前の AttackNet（初期重みのベースライン）
		attack_x: 攻撃モデルの学習特徴量 (N, NUM_CLASSES)
		attack_y: 攻撃モデルの学習ラベル (N,) 1=IN, 0=OUT

	Returns:
		AttackModelAnalysisResult: metrics に載せる値と summary.json のパス
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

	# 学習データを用いた解析: 到達度 → 入力感度の順 (到達度が低ければ以降は参考値)
	fit = compute_fit_metrics(trained_model, attack_x, attack_y)
	summary["fit"] = fit.to_dict()

	sensitivity = compute_input_sensitivity(trained_model, attack_x)
	summary["input_sensitivity"] = summarize_input_sensitivity(
		sensitivity, trained.effective_path()
	)
	plot_input_sensitivity(sensitivity, model_dir)

	summary_path = model_dir / "summary.json"
	with open(summary_path, "w", encoding="utf-8") as f:
		json.dump(summary, f, indent=2, ensure_ascii=False)

	return AttackModelAnalysisResult(
		w1_relative_change=delta_summary["w1_relative_change"],
		fit=fit,
		summary_path=summary_path,
	)
