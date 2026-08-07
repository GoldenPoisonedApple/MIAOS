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
from src.server_client.models import CreateExperimentRequest
from src.server_client.types import UNSET


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
		self, shadow_models: list[nn.Module], target_model: nn.Module
	) -> tuple[float, float]:
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
		# ターゲットモデルの予測結果
		target_preds, _ = MIA_Attack.get_predictions(target_model, attack_watermark_loader)
		target_preds = logit_scaling(target_preds).float()	# データセットと同じ前処理
		
		# 攻撃モデルで予測
		with torch.no_grad():
			attack_preds = attack_model(target_preds.to(cfg.DEVICE))
			# (1: 画像1枚分, 2: OUT/IN) なので [:, 1] で IN のスコアを取得
			# softmaxをとっているので IN のみで良い
			attack_scores = torch.softmax(attack_preds, dim=1)[:, 1].cpu().item()
   
		# 正解 ターゲットデータの装飾率
		attack_fraction = self.dataset.decoration_config.target_train_decoration.apply.fraction

		return attack_scores, attack_fraction


	# モデルの総合評価 オーバーライド
	def comprehensive_evaluate(self, scores: float, trues: float):
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
