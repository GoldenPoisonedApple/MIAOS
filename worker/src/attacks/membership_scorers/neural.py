import logging
import os
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

import src.core.config as cfg
from src.attacks.analysis.attack_model_analysis import analyze_attack_model
from src.attacks.membership_scorers.base import MembershipScore, ScoreScale
from src.attacks.mia_attack import MIA_Attack
from src.models.attack_model import AttackNet


class NeuralMembershipScorer:
	"""AttackNet を IN/OUT 2 クラス分類として学習し、softmax の IN 列を IN 確率とする。"""

	name = "neural"
	score_scale = ScoreScale.PROBABILITY

	def __init__(
		self,
		save_dir: str,
		logger: logging.Logger,
		batch_size: int,
		epochs: int,
	) -> None:
		self.save_dir = save_dir
		self.logger = logger
		self.batch_size = batch_size
		self.epochs = epochs
		self._model: AttackNet | None = None
		self._diagnostics: dict[str, Any] = {}

	def fit(self, in_feats: np.ndarray, out_feats: np.ndarray) -> None:
		"""in_feats, out_feats: (n_pairs, K, C)。K 枚それぞれを独立した学習サンプルとして展開する。"""
		num_classes = in_feats.shape[-1]
		# 結合: (n_pairs, K, C) -> (n_pairs * K, C)
		# np.ascontiguousarray: 連続したメモリ領域に変換
		in_x = torch.from_numpy(np.ascontiguousarray(in_feats)).float().reshape(-1, num_classes)
		out_x = torch.from_numpy(np.ascontiguousarray(out_feats)).float().reshape(-1, num_classes)
		attack_x = torch.cat([in_x, out_x])	# (n_pairs * K * 2, C)
		# ラベル作成
		in_labels = torch.ones(in_x.shape[0], dtype=torch.long)
		out_labels = torch.zeros(out_x.shape[0], dtype=torch.long)
		attack_y = torch.cat([in_labels, out_labels])

		# 攻撃モデルのデータセット作成
		attack_dataset = TensorDataset(attack_x, attack_y)
		attack_loader = DataLoader(
			attack_dataset,
			batch_size=self.batch_size,
			shuffle=True,
			num_workers=0,
			pin_memory=cfg.DEVICE.type == "cuda",
		)

		# 攻撃モデルの作成
		attack_model = AttackNet(input_dim=num_classes).to(cfg.DEVICE)
		# 初期重みを保存
		init_attack_model = AttackNet(input_dim=num_classes)
		init_attack_model.load_state_dict(attack_model.state_dict()) # attack_modelの初期重みをinit_attack_modelにコピー
		init_path = os.path.join(self.save_dir, cfg.ATTACK_MODEL_INIT_NAME)
		torch.save(init_attack_model.state_dict(), init_path)
		self.logger.info(f"Attack Model (init) saved -> {init_path}")

		# 攻撃モデルの訓練
		attack_model = MIA_Attack.train_model(
			attack_model, attack_loader, self.epochs
		)

		# 攻撃モデルの保存
		model_path = os.path.join(self.save_dir, cfg.ATTACK_MODEL_NAME)
		torch.save(attack_model.state_dict(), model_path)
		self.logger.info(f"Attack Model saved -> {model_path}")

		analysis_dir = os.path.join(self.save_dir, cfg.ATTACK_MODEL_ANALYSIS_DIR)
		# 攻撃モデルの内部表現解析（重み差分 + 学習データ上の到達度・入力感度）
		analysis = analyze_attack_model(
			attack_model,
			analysis_dir,
			init_model=init_attack_model,
			attack_x=attack_x,
			attack_y=attack_y,
		)
		self.logger.info(
			f"Attack Model fit -> Acc: {analysis.fit.accuracy:.4f}, Loss: {analysis.fit.loss:.4f} "
			f"(IN: {analysis.fit.in_accuracy}, OUT: {analysis.fit.out_accuracy}, N={analysis.fit.num_samples})"
		)
		self.logger.info(f"Attack Model analysis saved -> {analysis_dir}")
		self._diagnostics = {
			"w1_relative_change": analysis.w1_relative_change,
			"attack_model_train_acc": analysis.fit.accuracy,
			"attack_model_train_loss": analysis.fit.loss,
			"attack_model_train_in_acc": analysis.fit.in_accuracy,
			"attack_model_train_out_acc": analysis.fit.out_accuracy,
		}
		attack_model.eval()
		self._model = attack_model

	def score(self, feats: np.ndarray) -> MembershipScore:
		"""feats: (K, C) → value: K 枚の IN 確率の平均, per_image: (K,) IN 確率"""
		if self._model is None:
			raise RuntimeError("NeuralMembershipScorer.fit must be called before score")
		x = torch.from_numpy(np.ascontiguousarray(feats)).float().to(cfg.DEVICE)
		with torch.no_grad():
			attack_preds = self._model(x)
			# (K: 画像枚数, 2: OUT/IN) なので [:, 1] で IN のスコアを取得
			# softmaxをとっているので IN のみで良い
			probs = torch.softmax(attack_preds, dim=1)[:, 1]
		per_image = probs.cpu().numpy().astype(np.float64)
		# K 枚を独立に推定しているため、集約は IN 確率の平均とする
		return MembershipScore(value=float(per_image.mean()), per_image=per_image)

	def diagnostics(self) -> dict[str, Any]:
		return dict(self._diagnostics)
