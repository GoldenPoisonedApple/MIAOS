import torch
import torch.nn as nn
from torch.utils.data import DataLoader

import src.core.config as cfg
from src.attacks.lf_mia import LF_MIA, LF_MIA_TARGET_FRACTIONS
from src.attacks.mia_attack import MIA_Attack
from src.attacks.mia_lira_common import logit_scaling
from src.server_client.types import UNSET


# Local Feature MIA（複数画像合成版）
class LF_Mult_MIA(LF_MIA):
	"""
	攻撃用透かしを target test 画像 K 枚に合成し、各モデルの出力 K 本を
	それぞれ独立した学習サンプルとして攻撃モデルを学習する（案3: サンプル数を K 倍）。

	同じ K 枚が IN / OUT 両群に現れるため画像内容はラベルに対して無情報であり、
	攻撃モデルは透かしが出力に与える差分を使わざるを得ない。

	シャドー・ターゲットの学習は LF_MIA をそのまま継承し、attack のみ置き換える。
	"""

	# 合成画像枚数 K の取得
	def _num_images(self) -> int:
		"""hyperparameters.attack_num_images を返す（未指定時はエラー）"""
		hyperparameters = self.settings.hyperparameters
		if hyperparameters is UNSET or hyperparameters is None:
			raise ValueError("attack_num_images is not set in hyperparameters")
		hp = hyperparameters.to_dict()
		return int(hp.get("attack_num_images"))

	# 特徴抽出（テンプレートメソッド。サブクラスで差し替える）
	def _extract_features(
		self,
		model: nn.Module,
		decorated_loader: DataLoader,
		plain_loader: DataLoader,
	) -> torch.Tensor:
		"""
		1 モデルから攻撃モデル用の特徴量 (K, NUM_CLASSES) を抽出する。
		本クラスでは透かし合成画像に対する softmax を logit 変換したものを返す。
		Args:
				model: 特徴を抽出するモデル（シャドーまたはターゲット）
				decorated_loader: 透かし合成済み画像 K 枚
				plain_loader: 素の画像 K 枚（本クラスでは未使用。差分版のためのフック）
		Returns:
				features: (K, NUM_CLASSES) float32
		"""
		preds, _ = MIA_Attack.get_predictions(model, decorated_loader)
		# logit 変換: 確率のまま学習するより変化が大きく、差分版では log 空間での引き算が意味を持つ
		return logit_scaling(preds).float()

	# LF_Mult_MIA Attack
	def attack(
		self, shadow_models: list[nn.Module], target_model: list[nn.Module]
	) -> tuple[list[float], list[float]]:
		num_images = self._num_images()
		num_in = int(self.settings.num_shadow_models / 2)
		self.logger.info(f"LF_Mult_MIA: num_images(K)={num_images}")

		# 攻撃用データローダー取得（透かし合成済み / 素の画像。K 枚を 1 バッチで返す）
		decorated_loader, plain_loader = self.dataset.get_attack_composite_dataloaders(
			num_images
		)

		# 特徴量抽出: IN シャドー（各 (K, C)）
		# K: 画像枚数, C: クラス数
		in_feats = []
		for i in range(num_in):
			shadow_model = shadow_models[i]
			in_feats.append(
				# Kサンプル分の特徴量を抽出
				self._extract_features(shadow_model, decorated_loader, plain_loader)
			)
			shadow_model.to("cpu")  # GPUメモリ節約

		# 特徴量抽出: OUT シャドー（各 (K, C)）
		out_feats = []
		for i in range(num_in):
			shadow_model = shadow_models[i + num_in]
			out_feats.append(
				self._extract_features(shadow_model, decorated_loader, plain_loader)
			)
			shadow_model.to("cpu")  # GPUメモリ節約

		# 結合: (K * N_in, C), (K * N_out, C)
		# attack_x: (K * shadow_models, C)
		attack_x = torch.cat(in_feats + out_feats)
		# ラベル: 1 モデルあたり K サンプルなので K 倍に伸ばす
		in_labels = torch.ones(num_images * len(in_feats), dtype=torch.long)
		out_labels = torch.zeros(num_images * len(out_feats), dtype=torch.long)
		attack_y = torch.cat([in_labels, out_labels])

		# 攻撃モデルの訓練
		attack_model = self._train_attack_model(attack_x, attack_y)

		# ------------- 攻撃 -------------
		attack_scores: list[float] = []  # K 枚の IN 確率の平均（LF_MIA の attack_score と同スケール）
		attack_scores_vars: list[float] = []  # K 枚の IN 確率の標本分散
		attack_all_scores: list[list[float]] = []  # K 枚それぞれの IN 確率（ターゲットごと）
		attack_fractions: list[float] = []
		attack_model.eval()
		for fraction, single_target_model in zip(LF_MIA_TARGET_FRACTIONS, target_model):
			# ターゲットモデルの特徴量（学習時と同じ前処理）
			target_feats = self._extract_features(
				single_target_model, decorated_loader, plain_loader
			)
			single_target_model.to("cpu")  # GPUメモリ節約

			# 攻撃モデルで予測
			with torch.no_grad():
				attack_preds = attack_model(target_feats.to(cfg.DEVICE))
				# (K: 画像枚数, 2: OUT/IN) なので [:, 1] で IN のスコアを取得
				# softmaxをとっているので IN のみで良い
				probs = torch.softmax(attack_preds, dim=1)[:, 1].cpu()

			score, var, all_scores = LF_Mult_MIA.aggregate_scores(probs)
			self.logger.info(
				f"Target fraction={fraction} -> score(mean)={score:.4f}, var={var:.6f}"
			)

			attack_scores.append(score)
			attack_scores_vars.append(var)
			attack_all_scores.append(all_scores)
			attack_fractions.append(fraction)

		# attack_score / attack_fraction は継承した comprehensive_evaluate が格納する
		self.metrics.update({
			"attack_num_images": num_images,
			"attack_scores_vars": attack_scores_vars,
			"attack_all_scores": attack_all_scores,
		})

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
