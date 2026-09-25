import logging
import os
from typing import Callable

import torch
import torch.nn as nn
from tqdm import trange

import src.core.config as cfg
from src.attacks.mia_attack import MIA_Attack
from torch.utils.data import TensorDataset
from torch.utils.data import DataLoader
from src.models.attack_model import AttackNet
from src.attacks.mia_lira_common import (
	logit_scaling,
)
from src.data.dataset import dataset
from src.data.decorations.config import with_fraction
from src.server_client.models import CreateExperimentRequest
from src.server_client.types import UNSET


# LF_MIA 用ターゲットモデルの装飾適用率スイープ
LF_MIA_TARGET_FRACTIONS = [
	1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.01, 0.001, 0.0,
]


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
				shadow_models: 訓練後のシャドーモデル
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

		for i in trange(len(LF_MIA_TARGET_FRACTIONS), desc="Target Models"):
			fraction_value = LF_MIA_TARGET_FRACTIONS[i]
			decoration_spec = with_fraction(base_spec, fraction_value)
			trainloader, testloader, num_train, num_test = (
				self.dataset.get_target_dataloaders(decoration_spec=decoration_spec)
			)
			self.logger.info(
				f"Target Model fraction={fraction_value} -> Train: {num_train}, Test: {num_test}"
			)

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

	def from_request(self, settings: CreateExperimentRequest) -> tuple[int, int]:
		hyperparameters = settings.hyperparameters
		if hyperparameters is UNSET or hyperparameters is None:
			return (cfg.ATTACK_MODEL_BATCH_SIZE, cfg.ATTACK_MODEL_EPOCHS)
		hp = hyperparameters.to_dict()
		return (
			hp.get("attack_model_batch_size", cfg.ATTACK_MODEL_BATCH_SIZE),
			hp.get("attack_model_epochs", cfg.ATTACK_MODEL_EPOCHS),
		)

	# LF_MIA Attack
	def attack(
		self, shadow_models: list[nn.Module], target_model: list[nn.Module]
	) -> tuple[list[float], list[float]]:
		# 攻撃用透かし画像のデータローダー取得（黒背景に合成済みの1枚）
		attack_watermark_loader = self.dataset.get_attack_watermark_dataloader()
  
		# 特徴量抽出
		in_preds = []
		for i in range(int(self.settings.num_shadow_models / 2)):
			shadow_model = shadow_models[i]
			preds, _ = MIA_Attack.get_predictions(shadow_model, attack_watermark_loader)
			preds = logit_scaling(preds).float()	# なんとなくロジット変換 機械学習の時の前処理として変化は大きい方がいいかなと思って
			in_preds.append(preds)
			
		out_preds = []
		for i in range(int(self.settings.num_shadow_models / 2)):
			shadow_model = shadow_models[i + int(self.settings.num_shadow_models / 2)]
			preds, _ = MIA_Attack.get_predictions(shadow_model, attack_watermark_loader)
			preds = logit_scaling(preds).float()	# なんとなくロジット変換 機械学習の時の前処理として変化は大きい方がいいかなと思って
			out_preds.append(preds)
			
		# ラベル作成
		in_labels = torch.ones(len(in_preds), dtype=torch.long)
		out_labels = torch.zeros(len(out_preds), dtype=torch.long)

		# 結合
		attack_x = torch.cat(in_preds + out_preds)
		attack_y = torch.cat([in_labels, out_labels])
  
		# 攻撃モデルのバッチサイズとエポック数の取得
		attack_model_batch_size, attack_model_epochs = self.from_request(self.settings)
  
		# データセットの作成
		attack_dataset = TensorDataset(attack_x, attack_y)
		attack_loader = DataLoader(
      		attack_dataset,
      		batch_size=attack_model_batch_size,
      		shuffle=True,
      		num_workers=0,
      		pin_memory=cfg.DEVICE.type == "cuda",
    	)
		# 攻撃モデルの訓練
		attack_model = AttackNet(input_dim=cfg.NUM_CLASSES).to(cfg.DEVICE)
		attack_model = MIA_Attack.train_model(
			attack_model, attack_loader, attack_model_epochs
		)
		# 攻撃モデルの保存
		torch.save(
			attack_model.state_dict(), os.path.join(self.MODEL_SAVE_DIR, cfg.ATTACK_MODEL_NAME)
		)
		self.logger.info(
			f"Attack Model saved -> {os.path.join(self.MODEL_SAVE_DIR, cfg.ATTACK_MODEL_NAME)}"
		)
  
		# ------------- 攻撃 -------------
		attack_scores: list[float] = []
		attack_fractions: list[float] = []
		for fraction, single_target_model in zip(LF_MIA_TARGET_FRACTIONS, target_model):
			# ターゲットモデルの予測結果
			target_preds, _ = MIA_Attack.get_predictions(
				single_target_model, attack_watermark_loader
			)
			target_preds = logit_scaling(target_preds).float()	# データセットと同じ前処理

			# 攻撃モデルで予測
			with torch.no_grad():
				attack_preds = attack_model(target_preds.to(cfg.DEVICE))
				# (1: 画像1枚分, 2: OUT/IN) なので [:, 1] で IN のスコアを取得
				# softmaxをとっているので IN のみで良い
				score = torch.softmax(attack_preds, dim=1)[:, 1].cpu().item()

			attack_scores.append(score)
			attack_fractions.append(fraction)

		return attack_scores, attack_fractions


	# モデルの総合評価 オーバーライド
	def comprehensive_evaluate(self, scores: list[float], trues: list[float]):
		self.metrics.update({
			"attack_score": scores,
			"attack_fraction": trues,
			"global_auc": None,
			"tpr_at_001_fpr": None,
			"threshold_at_001_fpr": None,
			"tpr_at_01_fpr": None,
			"threshold_at_01_fpr": None,
			"tpr_at_1_fpr": None,
			"threshold_at_1_fpr": None,
		})
		return self.metrics
