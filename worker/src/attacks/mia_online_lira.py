import logging
import os
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
from scipy.stats import norm
from tqdm import trange

import src.core.config as cfg
from src.attacks.mia_attack import MIA_Attack
from src.attacks.mia_lira_common import (
	extract_correct_class_logits,
	extract_shadow_logits_matrix,
	plot_sample_shadow_dist_grid,
	plot_score_distributions,
	split_online_lira_sample_logits,
)
from src.data.dataset import dataset
from src.server_client.models import CreateExperimentRequest


# 最尤度攻撃(LiRA) — Online 版
class MIA_OnlineLiRA(MIA_Attack):
	def __init__(
		self,
		dataset: dataset,
		MODEL_SAVE_DIR: str,
		logger: logging.Logger,
		settings: CreateExperimentRequest,
	):
		super().__init__(dataset, MODEL_SAVE_DIR, logger, settings)
		self._keep_matrix: np.ndarray | None = None	# シャドーモデルにおいて、対象データがINかOUTかの行列

	def _get_keep_matrix(self) -> np.ndarray:
		"""各シャドーモデルにおいて、対象データがINかOUTかの行列を取得"""
		if self._keep_matrix is None:
			self._keep_matrix = self.dataset.build_online_lira_keep_matrix(
				self.settings.num_shadow_models,
				self.settings.seed,
			)
		return self._keep_matrix

	def _compute_online_lira_scores(
		self,
		target_logits: np.ndarray,
		shadow_logits: np.ndarray,
		keep_matrix: np.ndarray,
	) -> np.ndarray:
		"""
		Online LiRA スコア（Algorithm 1 行 15: 尤度比）を計算する。
		Args:
						target_logits: shape (num_samples,)
						shadow_logits: shape (num_shadows, num_samples)
						keep_matrix: shape (num_shadows, num_samples), True = IN
		Returns:
						lira_scores
		"""
		num_shadows, num_samples = shadow_logits.shape
		if num_shadows < 2:
			raise ValueError(
				"Online LiRA requires at least 2 shadow models (IN and OUT distributions)."
			)
		if keep_matrix.shape != shadow_logits.shape:
			raise ValueError(
				f"keep_matrix shape {keep_matrix.shape} does not match "
				f"shadow_logits shape {shadow_logits.shape}"
			)

		lira_scores = np.zeros(num_samples, dtype=np.float64)

		# 各サンプルにおいて、IN/OUTのロジットを計算
		for j in range(num_samples):
			in_logits, out_logits = split_online_lira_sample_logits(
				shadow_logits, keep_matrix, j
			)
			if len(in_logits) == 0 or len(out_logits) == 0:
				raise ValueError(
					f"Sample {j}: need both IN and OUT shadow confidences "
					f"(got {len(in_logits)} IN, {len(out_logits)} OUT)."
				)
			# IN/OUTのロジットの平均と標準偏差を計算
			mu_in = np.mean(in_logits)
			std_in = np.std(in_logits) + 1e-8
			mu_out = np.mean(out_logits)
			std_out = np.std(out_logits) + 1e-8
			# pdf: 確率密度, logpdf: 確率密度の対数: 数値的に安定しているため使用
			# 尤度比: データがINである確率 / データがOUTである確率
			logpdf_in = norm.logpdf(target_logits[j], mu_in, std_in)  # INの分布における確率密度
			logpdf_out = norm.logpdf(target_logits[j], mu_out, std_out)  # OUTの分布における確率密度
			lira_scores[j] = logpdf_in - logpdf_out  # 尤度比 logなので引き算 1に近いほどメンバーである可能性が高い

		return lira_scores

	# シャドーモデルの訓練 オーバーライド（Online LiRA: クエリサンプルの IN/OUT を追跡）
	def train_shadow_models(self, model_factory: Callable[[], nn.Module]):
		"""
		シャドーモデルの訓練
		各シャドーモデルはクエリサンプルの一部を学習集合に含める（keep 行列で制御）。
		"""
		# 対象データのidx取得
		query_indices = self.dataset.get_attack_query_indices()
		keep_matrix = self._get_keep_matrix()

		shadow_models = []
		state_dicts = []
		train_accs = []
		test_accs = []
		# シャドーモデルの訓練
		for i in trange(self.settings.num_shadow_models, desc="Shadow Models"):
			# シャドーモデルのデータローダーを取得
			shadow_train_loader, shadow_test_loader, _, _ = (
				self.dataset.get_online_lira_shadow_dataloader(
					seed=i,
					query_indices=query_indices,
					query_keep=keep_matrix[i],
				)
			)
			shadow_model = model_factory().to(cfg.DEVICE)
			shadow_model = MIA_Attack.train_model(
				shadow_model, shadow_train_loader, self.settings.max_epochs
			)
			shadow_models.append(shadow_model)
			state_dicts.append(shadow_model.state_dict())
			# 評価
			train_acc = MIA_Attack.get_accuracy(shadow_model, shadow_train_loader)
			test_acc = MIA_Attack.get_accuracy(shadow_model, shadow_test_loader)
			self.logger.info(f"Shadow Model {i} -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})")
			train_accs.append(train_acc)
			test_accs.append(test_acc)
			
			shadow_model.to("cpu")  # GPUメモリ節約

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

	# LiRA Attack
	# Online LiRA
	def attack(
		self, shadow_models: list[nn.Module], target_model: nn.Module
	) -> tuple[np.ndarray, np.ndarray]:
		keep_matrix = self._get_keep_matrix()

		# 対象データのデータローダー取得
		target_train_loader, target_test_loader, train_size, test_size = (
			self.dataset.get_eval_target_dataloaders()
		)

		# ------------- シャドーモデルから検証データの IN/OUT 分布を推定 -------------
		# (num_shadows, num_samples) 正解ラベル確率のロジット 行列
		shadow_logits = extract_shadow_logits_matrix(
			shadow_models,
			target_train_loader,
			target_test_loader,
			self.settings.num_shadow_models,
		)

		# ------- ターゲットモデルから検証データ特徴量抽出 ---------------
		# (num_samples,) 正解ラベル確率のロジット 行列
		target_logits, _, _ = extract_correct_class_logits(
			target_model, target_train_loader, target_test_loader
		)

		# Online LiRA スコア(尤度比)を計算
		lira_scores = self._compute_online_lira_scores(
			target_logits,
			shadow_logits,
			keep_matrix,
		)

		# ラベルを結合 メンバ、非メンバ
		lira_trues = np.concatenate([np.ones(train_size), np.zeros(test_size)])

		# サンプルデータの分布を保存
		plot_sample_shadow_dist_grid(
			model_save_dir=self.MODEL_SAVE_DIR,
			logger=self.logger,
			dataset_obj=self.dataset,
			shadow_logits=shadow_logits,
			target_logits=target_logits,
			train_size=train_size,
			keep_matrix=keep_matrix,
		)

		# スコア分布を保存
		plot_score_distributions(
			model_save_dir=self.MODEL_SAVE_DIR,
			logger=self.logger,
			variant="online",
			lira_scores=lira_scores,
			lira_trues=lira_trues,
		)

		return lira_scores, lira_trues
