import logging
import os
from typing import Any, Callable

import numpy as np
import torch
import torch.nn as nn
from tqdm import trange

import src.core.config as cfg
from src.attacks.mia_attack import MIA_Attack
from src.attacks.mia_lira_common import (
	logit_scaling,
)
from src.attacks.analysis.attack_score_distribution import (
	TargetScoreEntry,
	analyze_attack_score_distribution,
)
from src.attacks.analysis.shadow_pair_effect_analysis import analyze_shadow_pair_effects
from src.attacks.analysis.target_attack_sign_output import (
	TargetAttackSignEntry,
	analyze_target_attack_sign_output,
)
from src.attacks.membership_scorers import (
	MembershipScorerConfig,
	build_membership_scorer,
)
from src.data.dataset import dataset
from src.data.decorations.config import with_fraction
from src.server_client.models import CreateExperimentRequest
from src.server_client.types import UNSET


# LF_MIA 用ターゲットモデルの装飾適用率スイープ
LF_MIA_TARGET_FRACTIONS = [
	1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.01, 0.001,
	# fraction=0.0 を複数学習する場合は初期化 RNG のみずらす（train_target_model 参照）
	0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
]


def _reset_target_model_init_rng(seed: int) -> None:
	"""装飾適用率スイープの各ターゲットモデルが同一初期重みから学習を始めるよう RNG を固定する。"""
	torch.manual_seed(seed)
	if torch.cuda.is_available():
		torch.cuda.manual_seed_all(seed)


# Local Feature MIA
class LF_MIA(MIA_Attack):
	def __init__(
		self,
		dataset: dataset,
		MODEL_SAVE_DIR: str,
		logger: logging.Logger,
		settings: CreateExperimentRequest,
	):
		super().__init__(dataset, MODEL_SAVE_DIR, logger, settings)

	# シャドーモデルの訓練 オーバーライド
	def train_shadow_models(self, model_factory: Callable[[], nn.Module]):
		"""
		シャドーモデルの訓練
		Args:
				shadow_model: シャドーモデル
		Returns:
				shadow_models: 訓練後のシャドーモデル IN, OUTの順、半々
		"""
		# シャドーモデルの訓練
		shadow_models = []
		state_dicts = []
		train_accs = []
		test_accs = []
		# INモデルの訓練
		for i in trange(int(self.settings.num_shadow_models / 2), desc="Shadow IN Models"):
			shadow_train_loader, shadow_test_loader, _, _ = (
				self.dataset.get_shadow_dataloader(seed=i, is_decoration=True)
			)
			# モデルを作成
			shadow_model = model_factory().to(cfg.DEVICE)
			# モデルを訓練
			shadow_model = MIA_Attack.train_model(
				shadow_model, shadow_train_loader, self.settings.max_epochs
			)
			# リストを追加
			shadow_models.append(shadow_model)
			state_dicts.append(shadow_model.state_dict())
			# 評価
			train_acc = MIA_Attack.get_accuracy(shadow_model, shadow_train_loader)
			test_acc = MIA_Attack.get_accuracy(shadow_model, shadow_test_loader)
			self.logger.info(f"Shadow Model {i} -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})")
			train_accs.append(train_acc)
			test_accs.append(test_acc)
			
			shadow_model.to("cpu")  # GPUメモリ節約

		# OUTモデルの訓練
		for i in trange(int(self.settings.num_shadow_models / 2), desc="Shadow OUT Models"):
			shadow_train_loader, shadow_test_loader, _, _ = (
				self.dataset.get_shadow_dataloader(seed=i, is_decoration=False)
			)
			# モデルを作成
			shadow_model = model_factory().to(cfg.DEVICE)
			# モデルを訓練
			shadow_model = MIA_Attack.train_model(
				shadow_model, shadow_train_loader, self.settings.max_epochs
			)
			# リストを追加
			shadow_models.append(shadow_model)
			state_dicts.append(shadow_model.state_dict())
			# 評価
			train_acc = MIA_Attack.get_accuracy(shadow_model, shadow_train_loader)
			test_acc = MIA_Attack.get_accuracy(shadow_model, shadow_test_loader)
			self.logger.info(f"Shadow Model {i} -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})")
			train_accs.append(train_acc)
			test_accs.append(test_acc)
			
			shadow_model.to("cpu")  # GPUメモリ節約

		# モデルの保存
		torch.save(
			state_dicts, os.path.join(self.MODEL_SAVE_DIR, cfg.SHADOW_MODEL_NAME)
		)
		self.logger.info(
			f"Shadow Models saved -> {os.path.join(self.MODEL_SAVE_DIR, cfg.SHADOW_MODEL_NAME)}"
		)
		# 指標の更新
		self.metrics.update({
			"shadow_train_accs": train_accs,
			"shadow_test_accs": test_accs,
			"shadow_acc_gaps": [train_acc - test_acc for train_acc, test_acc in zip(train_accs, test_accs)],
		})

		return shadow_models

	# ターゲットモデルの訓練（装飾適用率スイープ）オーバーライド
	def train_target_model(self, model_factory: Callable[[], nn.Module]) -> list[nn.Module]:
		"""
		装飾適用率ごとにターゲットモデルを訓練する。
		Args:
				model_factory: ターゲットモデル生成関数
		Returns:
				target_models: 訓練後のターゲットモデル（装飾適用率ごと）
		"""
		base_spec = self.dataset.decoration_config.target_train_decoration
		if base_spec is None:
			raise ValueError("target_train_decoration is required for LF_MIA")

		target_models = []
		state_dicts = []
		train_accs = []
		test_accs = []

		zero_run_idx = 0
		for i in trange(len(LF_MIA_TARGET_FRACTIONS), desc="Target Models"):
			fraction_value = LF_MIA_TARGET_FRACTIONS[i]
			decoration_spec = with_fraction(base_spec, fraction_value)
			trainloader, testloader, num_train, num_test = (
				self.dataset.get_target_dataloaders(decoration_spec=decoration_spec)
			)
			self.logger.info(
				f"Target Model fraction={fraction_value} -> Train: {num_train}, Test: {num_test}"
			)

			# fraction 間で初期重みを揃え、装飾サブセットの効果だけを比較可能にする
			base_seed = int(self.settings.seed)
			if fraction_value == 0.0:
				# 1 本目の 0.0 は従来どおり base_seed。追加の 0.0 だけ初期化シードをずらす。
				init_seed = base_seed + zero_run_idx
				zero_run_idx += 1
			else:
				init_seed = base_seed
			_reset_target_model_init_rng(init_seed)
			target_model = model_factory().to(cfg.DEVICE)
			target_model = MIA_Attack.train_model(
				target_model, trainloader, self.settings.max_epochs
			)
			train_acc = MIA_Attack.get_accuracy(target_model, trainloader)
			test_acc = MIA_Attack.get_accuracy(target_model, testloader)
			self.logger.info(
				f"Target Model fraction={fraction_value} -> "
				f"Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})"
			)

			target_models.append(target_model)
			state_dicts.append(target_model.state_dict())
			train_accs.append(train_acc)
			test_accs.append(test_acc)
			target_model.to("cpu")  # GPUメモリ節約

		torch.save(
			state_dicts, os.path.join(self.MODEL_SAVE_DIR, cfg.TARGET_MODEL_NAME)
		)
		self.logger.info(
			f"Target Models saved -> {os.path.join(self.MODEL_SAVE_DIR, cfg.TARGET_MODEL_NAME)}"
		)
		self.metrics.update({
			"target_train_accs": train_accs,
			"target_test_accs": test_accs,
			"target_acc_gaps": [
				train_acc - test_acc for train_acc, test_acc in zip(train_accs, test_accs)
			],
		})

		return target_models

	# 攻撃モデル（メンバシップ推定器）の設定取得
	def _membership_scorer_config(self) -> MembershipScorerConfig:
		hyperparameters = self.settings.hyperparameters
		if hyperparameters is UNSET or hyperparameters is None:
			return MembershipScorerConfig()
		return MembershipScorerConfig.from_hyperparameters(hyperparameters.to_dict())

	# モデルに対する特徴量抽出関数の構築（テンプレートメソッド。サブクラスで差し替える）
	def _build_probe(self) -> Callable[[nn.Module], torch.Tensor]:
		"""
		1 モデルからプローブ特徴 (K, NUM_CLASSES) を返す callable を作る。
		本クラスは黒背景に合成した攻撃用透かし 1 枚（K=1）を入力する。
		"""
		# 攻撃用透かし画像のデータローダー取得（黒背景に合成済みの1枚）
		attack_watermark_loader = self.dataset.get_attack_watermark_dataloader()

		def probe(model: nn.Module) -> torch.Tensor:
			preds, _ = MIA_Attack.get_predictions(model, attack_watermark_loader)
			return logit_scaling(preds).float()	# なんとなくロジット変換 機械学習の時の前処理として変化は大きい方がいいかなと思って

		return probe

	# サブクラス固有の追加 metrics
	def _extra_attack_metrics(self) -> dict[str, Any]:
		return {}

	# ターゲットモデルへの攻撃透かし入力結果を可視化・保存
	def _output_target_attack_sign_analysis(
		self,
		target_models: list[nn.Module],
	) -> None:
		# 攻撃用透かし画像のデータローダー取得（黒背景に合成済みの1枚）
		attack_watermark_loader = self.dataset.get_attack_watermark_dataloader()

		entries: list[TargetAttackSignEntry] = []
		for fraction, model in zip(LF_MIA_TARGET_FRACTIONS, target_models, strict=True):
			preds, _ = MIA_Attack.get_predictions(model, attack_watermark_loader)
			probs = preds.squeeze(0).detach().cpu().numpy()
			model.to("cpu")  # GPUメモリ節約

			entries.append(
				TargetAttackSignEntry(
					fraction=fraction,
					probs=probs,
				)
			)

		output_dir = os.path.join(
			self.MODEL_SAVE_DIR, cfg.TARGET_ATTACKSIGN_OUTPUT_DIR
		)
		summary_path = analyze_target_attack_sign_output(entries, output_dir)
		self.logger.info(f"Target attack sign output saved -> {output_dir}")
		self.logger.info(f"Target attack sign summary -> {summary_path}")

	def _collect_shadow_features(
		self,
		shadow_models: list[nn.Module],
		probe: Callable[[nn.Module], torch.Tensor],
	) -> tuple[np.ndarray, np.ndarray]:
		"""IN/OUT シャドーのプローブ特徴 (n_pairs, K, NUM_CLASSES) を返す。シャドーは IN, OUT の順で半々。"""
		num_in = int(self.settings.num_shadow_models / 2)

		def extract(model: nn.Module) -> np.ndarray:
			feats = probe(model).detach().cpu().numpy()
			model.to("cpu")  # GPUメモリ節約
			return feats

		in_feats = [extract(shadow_models[i]) for i in range(num_in)]
		out_feats = [extract(shadow_models[i + num_in]) for i in range(num_in)]
		return np.stack(in_feats), np.stack(out_feats)

	def _run_shadow_pair_effect_analysis(
		self, in_features: np.ndarray, out_features: np.ndarray
	) -> None:
		"""シャドー IN/OUT ペアのクラス別装飾効果量解析を実行する。特徴は (n_pairs, NUM_CLASSES)。"""
		output_dir = os.path.join(self.MODEL_SAVE_DIR, cfg.SHADOW_PAIR_EFFECT_DIR)
		result = analyze_shadow_pair_effects(
			in_features,
			out_features,
			output_dir,
			random_state=int(self.settings.seed),
		)
		self.logger.info(f"Shadow pair effect analysis saved -> {output_dir}")
		self.logger.info(f"Shadow pair effect summary -> {result.summary_path}")
		self.metrics.update({
			"shadow_pair_global_permutation_pvalue": result.global_permutation_pvalue,
			"shadow_pair_num_significant_fdr": result.num_significant_fdr,
		})

	# LF_MIA Attack
	def attack(
		self, shadow_models: list[nn.Module], target_model: list[nn.Module]
	) -> tuple[list[float], list[float]]:
		config = self._membership_scorer_config()
		self.logger.info(f"Membership scorer={config.kind}")
		probe = self._build_probe()

		# 特徴量抽出: (n_pairs, K, C)
		in_feats, out_feats = self._collect_shadow_features(shadow_models, probe)

		# 攻撃モデルの訓練
		scorer = build_membership_scorer(
			config, save_dir=self.MODEL_SAVE_DIR, logger=self.logger
		)
		scorer.fit(in_feats, out_feats)
		diagnostics = scorer.diagnostics()
		self.logger.info(f"Membership scorer diagnostics -> {diagnostics}")

		# ------------- 攻撃 -------------
		attack_scores: list[float] = []  # K 枚の IN 確率の平均
		attack_scores_vars: list[float] = []  # K 枚の IN 確率の標本分散（K=1 では 0）
		attack_all_scores: list[list[float]] = []  # K 枚それぞれの IN 確率（ターゲットごと）
		attack_fractions: list[float] = []
		for fraction, single_target_model in zip(LF_MIA_TARGET_FRACTIONS, target_model, strict=True):
			# ターゲットモデルの特徴量（シャドーと同じ前処理）
			target_feats = probe(single_target_model).detach().cpu().numpy()
			single_target_model.to("cpu")  # GPUメモリ節約

			# 攻撃モデルで予測
			probs = torch.from_numpy(scorer.score(target_feats))
			score, var, all_scores = LF_MIA.aggregate_scores(probs) # K枚のIN確率の平均, 標本分散, 全値のリスト
			self.logger.info(
				f"Target fraction={fraction} -> score(mean)={score:.4f}, var={var:.6f}"
			)

			attack_scores.append(score)
			attack_scores_vars.append(var)
			attack_all_scores.append(all_scores)
			attack_fractions.append(fraction)

		# attack_score / attack_fraction は comprehensive_evaluate が格納する
		# attack_all_scores は値が多く DB に載せられないため、metrics ではなくファイルで出力する
		self.metrics.update({
			"membership_scorer": config.kind,
			**diagnostics,
			"attack_scores_vars": attack_scores_vars,
			**self._extra_attack_metrics(),
		})

		# ターゲットごとの K 枚分のスコア分布の可視化
		score_entries = [
			TargetScoreEntry(fraction=fraction, scores=np.asarray(all_scores))
			for fraction, all_scores in zip(attack_fractions, attack_all_scores, strict=True)
		]
		self._output_attack_score_distribution(score_entries)

		# K 枚分のスコア全体での ROC（fraction>0 を IN、fraction=0 を OUT）
		self._evaluate_all_scores_roc(score_entries)

		# ターゲットモデルへの攻撃透かし入力結果の可視化
		self._output_target_attack_sign_analysis(target_model)

		# シャドー IN/OUT ペアのクラス別装飾効果量解析（既存攻撃結果には影響しない）
		# K 枚平均でペアあたり 1 ベクトルにする（再推論はしない）
		self._run_shadow_pair_effect_analysis(in_feats.mean(axis=1), out_feats.mean(axis=1))

		return attack_scores, attack_fractions

	# K 枚分の IN 確率を集約
	@staticmethod
	def aggregate_scores(probs: torch.Tensor) -> tuple[float, float, list[float]]:
		"""
		K 枚分の IN 確率 (K,) を集約する。
		Args:
				probs: 各画像に対する IN 確率 (K,)
		Returns:
				score: 平均（LF_MIA の attack_score と比較可能な確率スケール）
				var: 標本分散（K=1 のときは 0.0）
				all_scores: 全値のリスト（log-odds 平均など別の集約は事後計算する）
		"""
		# detach: 計算グラフから切り離す: メタデータ削除
		# float: 浮動小数点数に変換
		# flatten: 1次元に平坦化
		probs = probs.detach().float().flatten()
		score = probs.mean().item()
		# K=1 では unbiased 分散が NaN になるため 0.0 とする
		var = probs.var(unbiased=True).item() if probs.numel() > 1 else 0.0
		return score, var, probs.tolist()

	# ターゲットごとのスコア分布を可視化・保存
	def _output_attack_score_distribution(self, entries: list[TargetScoreEntry]) -> None:
		output_dir = os.path.join(self.MODEL_SAVE_DIR, cfg.ATTACK_SCORE_DISTRIBUTION_DIR)
		scores_path = analyze_attack_score_distribution(entries, output_dir)
		self.logger.info(f"Attack score distribution saved -> {output_dir}")
		self.logger.info(f"Attack score raw data -> {scores_path}")

	# K 枚分のスコア全体での ROC 評価
	def _evaluate_all_scores_roc(self, entries: list[TargetScoreEntry]) -> None:
		# 各ターゲットの K 個のスコアに、そのターゲットのラベル（fraction>0 なら IN=1）を付けて展開
		scores = np.concatenate([entry.scores for entry in entries])
		trues = np.concatenate([
			np.full(entry.scores.size, 1 if entry.is_in else 0) for entry in entries
		])
		roc_metrics, fpr, tpr, roc_auc = MIA_Attack.compute_roc_metrics(trues, scores)

		roc_plot_path = os.path.join(self.MODEL_SAVE_DIR, "roc_curve_all_scores.png")
		MIA_Attack.plot_roc_curve(
			fpr,
			tpr,
			roc_auc,
			roc_plot_path,
			"LF MIA ROC Curve over all per-image scores (Log-Log Scale)",
		)
		self.logger.info(f"Saved all-scores ROC curve plot to: {roc_plot_path}")
		self.log_roc_metrics(roc_metrics, header="--- Results (all per-image scores) ---")

		# global_auc -> all_scores_auc, tpr_at_1_fpr -> all_scores_tpr_at_1_fpr ...
		self.metrics.update({
			"all_scores_auc": roc_metrics["global_auc"],
			**{
				f"all_scores_{key}": value
				for key, value in roc_metrics.items()
				if key != "global_auc"
			},
		})

	# モデルの総合評価 オーバーライド
	def comprehensive_evaluate(self, scores: list[float], trues: list[float]):
		# trues には fraction が入る。fraction>0 を IN(1)、fraction=0 を OUT(0) とする
		labels = [1 if fraction > 0 else 0 for fraction in trues]
		roc_metrics, fpr, tpr, roc_auc = MIA_Attack.compute_roc_metrics(labels, scores)

		# ------------- ROC曲線描画 -------------
		roc_plot_path = os.path.join(self.MODEL_SAVE_DIR, "roc_curve.png")
		MIA_Attack.plot_roc_curve(
			fpr,
			tpr,
			roc_auc,
			roc_plot_path,
			"LF MIA ROC Curve over targets (Log-Log Scale)",
		)
		self.logger.info(f"Saved ROC curve plot to: {roc_plot_path}")
		self.log_roc_metrics(roc_metrics, header="--- Results (per-target mean scores) ---")

		self.metrics.update({
			"attack_score": scores,
			"attack_fraction": trues,
			**roc_metrics,
		})
		return self.metrics
