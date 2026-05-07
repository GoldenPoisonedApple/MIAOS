import numpy as np
import logging
from mia_attack import MIA_Attack
from dataset import dataset
import torch
import torch.nn as nn
from tqdm import trange
import config as cfg
from config import ExperimentConfig

# ROC曲線描画用に追加
import matplotlib
matplotlib.use('Agg') # GUIを持たないDocker環境での描画用バックエンド
import matplotlib.pyplot as plt
import os


# 最尤度攻撃(LiRA)
class MIA_LIRA(MIA_Attack):
	def __init__(self, dataset: dataset, MODEL_SAVE_DIR: str, logger: logging.Logger, config: ExperimentConfig):
		super().__init__(dataset, MODEL_SAVE_DIR, logger, config)

  
	# 正規分布に変換
	@staticmethod
	def logit_scaling(probs: torch.Tensor):
		"""
		正規分布に変換
		Args:
			probs: 予測結果確率(256*n,)
		Returns:
			torch.Tensor: ロジット変換後の予測結果確率(256*n,)
		"""
		# 丸め誤差回避
		probs = probs.to(torch.float64)
		# p=0 や p=1 による無限大を回避するための微小値クリッピング
		eps = 1e-10
		probs = torch.clamp(probs, eps, 1.0 - eps)
		return torch.log(probs / (1.0 - probs))


	# LiRA Attack
	def attack(self, shadow_models: list[nn.Module], target_model: nn.Module) -> tuple[np.ndarray, np.ndarray]:
		
		# ターゲットモデルの学習データとテストデータを取得 検証用
		target_train_loader, target_test_loader, _, _ = self.dataset.get_eval_target_dataloaders()

		# ------------- 特徴量抽出 -------------
		shadow_in_logits = []
		shadow_out_logits = []
		for i in trange(self.config.num_shadow_models, desc="Feature Extraction with Shadow Models"):
			# 予測値の抽出
			in_preds, in_labels = MIA_Attack.get_predictions(shadow_models[i], target_train_loader) # 訓練データ
			out_preds, out_labels = MIA_Attack.get_predictions(shadow_models[i], target_test_loader) # テストデータ
			shadow_models[i].to('cpu') # GPUメモリ節約

			# 正解クラスの確率抽出
			# torch.arange(len(target_l_in)): 0からlen(target_l_in)-1までのインデックスを作成
			# → つまりそのインデックスに対応する正解クラスインデックスが[]内で作成
			# → 確立達の中から、正解ラベルに対応する正解クラス確率が抽出される
			in_prob = in_preds[torch.arange(len(in_labels)), in_labels]
			out_prob = out_preds[torch.arange(len(out_labels)), out_labels]
			# ロジット変換
			in_logits = MIA_LIRA.logit_scaling(in_prob).numpy()
			out_logits = MIA_LIRA.logit_scaling(out_prob).numpy()
			# リストに追加
			shadow_in_logits.append(in_logits)
			shadow_out_logits.append(out_logits)
   
		# リストをNumpy配列に変換
		shadow_in_logits = np.array(shadow_in_logits)
		shadow_out_logits = np.array(shadow_out_logits)
		# シャドーモデル群から、サンプルごとの平均と標準偏差を計算
		shadow_in_means = np.mean(shadow_in_logits, axis=0) # メンバー
		shadow_in_stds = np.std(shadow_in_logits, axis=0) + 1e-8 # ゼロ除算防止
		shadow_out_means = np.mean(shadow_out_logits, axis=0) # 非メンバー
		shadow_out_stds = np.std(shadow_out_logits, axis=0) + 1e-8 # ゼロ除算防止

		# ------- 評価 ---------
		target_in_preds, target_in_labels = MIA_Attack.get_predictions(target_model, target_train_loader)
		target_out_preds, target_out_labels = MIA_Attack.get_predictions(target_model, target_test_loader)
		# 正解クラスの確率抽出
		# torch.arange(len(target_l_in)): 0からlen(target_l_in)-1までのインデックスを作成
		# → つまりそのインデックスに対応する正解クラスインデックスが[]内で作成
		# → 確立達の中から、正解ラベルに対応する正解クラス確率が抽出される
		target_in_prob = target_in_preds[torch.arange(len(target_in_labels)), target_in_labels]
		target_out_prob = target_out_preds[torch.arange(len(target_out_labels)), target_out_labels]
		# ロジット変換
		target_in_logits = MIA_LIRA.logit_scaling(target_in_prob).numpy()
		target_out_logits = MIA_LIRA.logit_scaling(target_out_prob).numpy()

		# 攻撃スコア = (ターゲットモデルの出力 - シャドーモデルの平均) / 標準偏差
		in_z_scores = (target_in_logits - shadow_in_means) / shadow_in_stds
		out_z_scores = (target_out_logits - shadow_out_means) / shadow_out_stds
  
		lira_scores = np.concatenate([in_z_scores, out_z_scores])
		lira_trues = np.concatenate([np.ones(len(in_z_scores)), np.zeros(len(out_z_scores))])

		# ------------- 可視化 -------------
		# スコアの最小値と最大値からビンの範囲を決定 (外れ値が大きすぎると見えなくなるためパーセンタイルでクリップ)
		min_val = np.percentile(lira_scores, 0.1)
		max_val = np.percentile(lira_scores, 99.9)
		bins = np.linspace(min_val, max_val, 100)
		# 密度(density=True)としてプロットし、2つの分布を比較しやすくする
		plt.figure(figsize=(10, 6))
		plt.hist(in_z_scores, bins=bins, alpha=0.6, color='royalblue', label='Members (IN)', density=True)
		plt.hist(out_z_scores, bins=bins, alpha=0.6, color='crimson', label='Non-Members (OUT)', density=True)
		# 情報追加
		plt.xlabel('Attack Score (Z-score)')
		plt.ylabel('Density')
		plt.title('Distribution of Attack Scores (Offline LiRA)')
		plt.legend(loc='upper right')
		plt.grid(True, linestyle='--', alpha=0.5)
		# 保存
		dist_plot_path = os.path.join(self.MODEL_SAVE_DIR, "score_distribution_lira.png")
		plt.savefig(dist_plot_path, dpi=300, bbox_inches='tight')
		plt.close()
		self.logger.info(f"Saved score distribution plot to: {dist_plot_path}")
  
		return lira_scores, lira_trues