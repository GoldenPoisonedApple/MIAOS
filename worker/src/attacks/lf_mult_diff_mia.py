from dataclasses import replace

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.attacks.analysis.probe_violin import ProbeViolinPanel, SignificanceTest
from src.attacks.lf_mult_mia import LF_Mult_MIA
from src.attacks.mia_attack import MIA_Attack
from src.attacks.mia_lira_common import logit_scaling


# Local Feature MIA（複数画像合成 + 差分特徴版）
class LF_Mult_Diff_MIA(LF_Mult_MIA):
	"""
	LF_Mult_MIA の特徴量を「透かしあり − 透かしなし」の logit 差分に置き換える。

	画像固有の出力成分を引き算で打ち消し、透かしに対するモデルの感度だけを残す
	（LiRA 系のキャリブレーションと同じ発想）。それ以外の学習・攻撃手順は LF_Mult_MIA と同一。
	"""

	# 特徴抽出 オーバーライド
	def _extract_features(
		self,
		model: nn.Module,
		decorated_loader: DataLoader,
		plain_loader: DataLoader,
	) -> torch.Tensor:
		"""
		差分特徴 logit(f(img + wm)) - logit(f(img)) を (K, NUM_CLASSES) で返す。
		decorated_loader と plain_loader は同じ K 枚を同じ順序で返す前提。
		"""
		decorated_preds, _ = MIA_Attack.get_predictions(model, decorated_loader)
		plain_preds, _ = MIA_Attack.get_predictions(model, plain_loader)
		# log 空間で引き算し、画像固有の成分を打ち消す
		diff = logit_scaling(decorated_preds) - logit_scaling(plain_preds)
		return diff.float()

	# バイオリン図の縦軸ラベル オーバーライド
	def _probe_feature_label(self) -> str:
		return "logit(decorated) - logit(plain)"

	# バイオリン図パネル構築 オーバーライド
	def _shadow_pair_violin_panels(
		self,
		shadow_models: list[nn.Module],
		in_feats: np.ndarray,
		out_feats: np.ndarray,
	) -> list[ProbeViolinPanel]:
		"""
		IN / OUT（decorated - plain）を 0 に対する 1 標本 Wilcoxon の検定対象にし、
		decorated / plain それぞれの IN / OUT パネルを追加する。
		decorated / plain は攻撃経路に触れないよう、解析用に再推論して取得する
		（get_attack_composite_dataloaders は seed で決定的なので攻撃と同じ K 枚になる）。
		"""
		panels = [
			replace(panel, significance=SignificanceTest.MODEL_LEVEL)
			if panel.name in ("in", "out")
			else panel
			for panel in super()._shadow_pair_violin_panels(shadow_models, in_feats, out_feats)
		]

		decorated_loader, plain_loader = self.dataset.get_attack_composite_dataloaders(
			self._num_images()
		)

		def logits(model: nn.Module, loader: DataLoader) -> np.ndarray:
			preds, _ = MIA_Attack.get_predictions(model, loader)
			model.to("cpu")  # GPUメモリ節約
			return logit_scaling(preds).float().detach().cpu().numpy()

		# シャドーは IN, OUT の順で半々
		num_in = int(self.settings.num_shadow_models / 2)
		groups = {
			"in": shadow_models[:num_in],
			"out": shadow_models[num_in : 2 * num_in],
		}
		for group, models in groups.items():
			for kind, loader in (("decorated", decorated_loader), ("plain", plain_loader)):
				panels.append(
					ProbeViolinPanel(
						name=f"{group}_{kind}",
						title=f"Shadow {group.upper()} probe features ({kind})",
						ylabel=f"logit({kind})",
						values=np.stack([logits(model, loader) for model in models]),
					)
				)
		return panels

	# ターゲットのバイオリン図パネル構築 オーバーライド
	def _target_probe_violin_panels(
		self,
		fractions: list[float],
		target_feats: list[np.ndarray],
	) -> list[ProbeViolinPanel]:
		"""
		攻撃特徴（decorated - plain）を 0 に対する 1 標本 Wilcoxon の検定対象にする。
		単一ターゲットはモデル単位の検定ができないため画像単位（1 モデルを固定した条件付き検定）、
		fraction=0 の統合パネルは複数モデルなのでモデル単位で検定する。
		"""
		return [
			replace(
				panel,
				significance=(
					SignificanceTest.IMAGE_LEVEL
					if panel.n_models == 1
					else SignificanceTest.MODEL_LEVEL
				),
			)
			for panel in super()._target_probe_violin_panels(fractions, target_feats)
		]
