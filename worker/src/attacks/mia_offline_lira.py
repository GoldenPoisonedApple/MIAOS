import logging

import numpy as np
import torch
import torch.nn as nn
from scipy.stats import norm

from src.attacks.mia_attack import MIA_Attack
from src.attacks.mia_lira_common import (
	extract_correct_class_logits,
	extract_shadow_logits_matrix,
	plot_offline_sample_shadow_out_distribution,
	plot_score_distributions,
)
from src.data.dataset import dataset
from src.server_client.models import CreateExperimentRequest


# 最尤度攻撃(LiRA) — Offline 版
class MIA_OfflineLiRA(MIA_Attack):
	def __init__(
		self,
		dataset: dataset,
		MODEL_SAVE_DIR: str,
		logger: logging.Logger,
		settings: CreateExperimentRequest,
	):
		super().__init__(dataset, MODEL_SAVE_DIR, logger, settings)

	# LiRA Attack
	# Offline LiRA
	def attack(
		self, shadow_models: list[nn.Module], target_model: nn.Module
	) -> tuple[np.ndarray, np.ndarray]:

		# ターゲットモデルの学習データとテストデータを取得 検証用
		target_train_loader, target_test_loader, train_size, test_size = (
			self.dataset.get_eval_target_dataloaders()
		)

		# ------------- シャドーモデルから検証データのOUT分布を推定 -------------
		# ターゲットデータを学習に使用しなかったモデルを選び出し、Out分布を推定(targetのデータはshadowモデルで一切学習していないため使用可能)
		# -------------------------------------
		shadow_out_logits = extract_shadow_logits_matrix(
			shadow_models,
			target_train_loader,
			target_test_loader,
			self.settings.num_shadow_models,
		)

		# ------- ターゲットモデルから検証データ特徴量抽出 ---------------
		# ターゲットモデルから、同じ検証したいデータのロジットを抽出
		# -------------------------------------
		target_logits, train_labels, test_labels = extract_correct_class_logits(
			target_model, target_train_loader, target_test_loader
		)

		# シャドーモデル群から、サンプルごとの平均と標準偏差を計算
		# axis=0: 列方向 サンプルごとの平均と標準偏差を計算
		shadow_out_means = np.mean(shadow_out_logits, axis=0)
		shadow_out_stds = np.std(shadow_out_logits, axis=0) + 1e-8  # ゼロ除算防止
		# -------------------------------------
		# 攻撃スコア計算
		# Λ = Pr[Z <= conf_obs] = Φ((conf_obs - μ_out) / σ_out)
		# スコアが μ_outより極端に高い -> 非メンバーである確率は低い → メンバーである可能性が高い
		# -------------------------------------
		z_scores = (target_logits - shadow_out_means) / shadow_out_stds
		# zスコアから累積確率を計算
		# → 非メンバーの分布の lira_scores%よりデータが離れている -> メンバーである可能性が高い
		lira_scores = norm.cdf(z_scores)

		# ラベルを結合 メンバ、非メンバ
		lira_trues = np.concatenate([np.ones(train_size), np.zeros(test_size)])

		# サンプルデータの分布を保存
		plot_offline_sample_shadow_out_distribution(
			model_save_dir=self.MODEL_SAVE_DIR,
			logger=self.logger,
			dataset_obj=self.dataset,
			shadow_out_logits=shadow_out_logits,
			target_logits=target_logits,
			train_size=train_size,
			sample_idx=0,
		)

		# スコア分布を保存
		plot_score_distributions(
			model_save_dir=self.MODEL_SAVE_DIR,
			logger=self.logger,
			variant="offline",
			lira_scores=lira_scores,
			lira_trues=lira_trues,
			z_scores=z_scores,
		)

		return lira_scores, lira_trues
