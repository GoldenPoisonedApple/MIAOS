from typing import Any, Callable

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.attacks.lf_mia import LF_MIA
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

	シャドー・ターゲットの学習は LF_MIA をそのまま継承し、attack のみ置き換える
	（attack 本体は LF_MIA と共通で、プローブ = 入力画像の作り方のみ置き換える）。
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

	# モデルに対する特徴量抽出関数の構築 オーバーライド
	def _build_probe(self) -> Callable[[nn.Module], torch.Tensor]:
		"""target test 画像 K 枚に攻撃用透かしを合成したものを入力する。"""
		num_images = self._num_images()
		self.logger.info(f"LF_Mult_MIA: num_images(K)={num_images}")

		# 攻撃用データローダー取得（透かし合成済み / 素の画像。K 枚を 1 バッチで返す）
		decorated_loader, plain_loader = self.dataset.get_attack_composite_dataloaders(
			num_images
		)

		def probe(model: nn.Module) -> torch.Tensor:
			return self._extract_features(model, decorated_loader, plain_loader)

		return probe

	def _extra_attack_metrics(self) -> dict[str, Any]:
		return {"attack_num_images": self._num_images()}
