import torch
import torch.nn as nn
from torch.utils.data import DataLoader

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
