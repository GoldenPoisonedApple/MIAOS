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
    ONLINE_LIRA_KEEP_NAME,
    extract_correct_class_logits,
    extract_shadow_logits_matrix,
    plot_score_distributions,
    save_lira_artifacts,
)
from src.data.dataset import dataset
from src.server_client.models import CreateExperimentRequest


def compute_online_lira_scores(
    target_logits: np.ndarray,
    shadow_logits: np.ndarray,
    keep_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Online LiRA スコア（Algorithm 1 行 15: 尤度比）を計算する。
    Args:
            target_logits: shape (num_samples,)
            shadow_logits: shape (num_shadows, num_samples)
            keep_matrix: shape (num_shadows, num_samples), True = IN
    Returns:
            lira_scores, shadow_in_means, shadow_out_means
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
    shadow_in_means = np.zeros(num_samples, dtype=np.float64)
    shadow_out_means = np.zeros(num_samples, dtype=np.float64)

    for j in range(num_samples):
        in_mask = keep_matrix[:, j]
        in_logits = shadow_logits[in_mask, j]
        out_logits = shadow_logits[~in_mask, j]
        if len(in_logits) == 0 or len(out_logits) == 0:
            raise ValueError(
                f"Sample {j}: need both IN and OUT shadow confidences "
                f"(got {len(in_logits)} IN, {len(out_logits)} OUT)."
            )
        mu_in = np.mean(in_logits)
        std_in = np.std(in_logits) + 1e-8
        mu_out = np.mean(out_logits)
        std_out = np.std(out_logits) + 1e-8
        shadow_in_means[j] = mu_in
        shadow_out_means[j] = mu_out
        # Λ = p(conf_obs | IN) / p(conf_obs | OUT)  （対数空間）
        lira_scores[j] = norm.logpdf(target_logits[j], mu_in, std_in) - norm.logpdf(
            target_logits[j], mu_out, std_out
        )

    return lira_scores, shadow_in_means, shadow_out_means


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
        self._keep_matrix: np.ndarray | None = None

    def _get_keep_matrix_path(self) -> str:
        return os.path.join(self.MODEL_SAVE_DIR, ONLINE_LIRA_KEEP_NAME)

    def _save_keep_matrix(self, keep_matrix: np.ndarray) -> None:
        np.save(self._get_keep_matrix_path(), keep_matrix)
        self.logger.info(
            f"Saved Online LiRA keep matrix to: {self._get_keep_matrix_path()}"
        )

    def _load_keep_matrix(self) -> np.ndarray:
        path = self._get_keep_matrix_path()
        if not os.path.exists(path):
            raise ValueError(
                f"Online LiRA requires keep matrix at '{path}'. "
                "Shadow models trained with Offline LiRA cannot be reused for Online LiRA."
            )
        return np.load(path)

    # シャドーモデルの訓練 オーバーライド（Online LiRA: クエリサンプルの IN/OUT を追跡）
    def train_shadow_models(self, model_factory: Callable[[], nn.Module]):
        """
        シャドーモデルの訓練
        各シャドーモデルはクエリサンプルの一部を学習集合に含める（keep 行列で制御）。
        """
        query_indices = self.dataset.get_attack_query_indices()
        keep_matrix = self.dataset.build_online_lira_keep_matrix(
            self.settings.num_shadow_models,
            self.settings.seed,
        )
        self._save_keep_matrix(keep_matrix)
        self._keep_matrix = keep_matrix

        shadow_models = []
        state_dicts = []
        for i in trange(self.settings.num_shadow_models, desc="Shadow Models"):
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
            shadow_model.to("cpu")  # GPUメモリ節約
            shadow_models.append(shadow_model)
            state_dicts.append(shadow_model.state_dict())
            # 評価
            # 未実装

        torch.save(
            state_dicts, os.path.join(self.MODEL_SAVE_DIR, cfg.SHADOW_MODEL_NAME)
        )
        self.logger.info(
            f"Shadow Models saved -> {os.path.join(self.MODEL_SAVE_DIR, cfg.SHADOW_MODEL_NAME)}"
        )
        return shadow_models

    # LiRA Attack
    # Online LiRA
    def attack(
        self, shadow_models: list[nn.Module], target_model: nn.Module
    ) -> tuple[np.ndarray, np.ndarray]:
        if self._keep_matrix is None:
            self._keep_matrix = self._load_keep_matrix()

        # ターゲットモデルの学習データとテストデータを取得 検証用
        target_train_loader, target_test_loader, train_size, test_size = (
            self.dataset.get_eval_target_dataloaders()
        )

        # ------------- シャドーモデルから検証データの IN/OUT 分布を推定 -------------
        shadow_logits = extract_shadow_logits_matrix(
            shadow_models,
            target_train_loader,
            target_test_loader,
            self.settings.num_shadow_models,
        )

        # ------- ターゲットモデルから検証データ特徴量抽出 ---------------
        target_logits, labels_1, labels_2 = extract_correct_class_logits(
            target_model, target_train_loader, target_test_loader
        )

        lira_scores, shadow_in_means, shadow_out_means = compute_online_lira_scores(
            target_logits,
            shadow_logits,
            self._keep_matrix,
        )

        lira_trues = np.concatenate([np.ones(train_size), np.zeros(test_size)])
        class_labels = torch.cat([labels_1, labels_2]).numpy()
        sample_global_indices = np.concatenate(
            [self.dataset.target_train_idx, self.dataset.target_test_idx]
        )

        save_lira_artifacts(
            model_save_dir=self.MODEL_SAVE_DIR,
            logger=self.logger,
            variant="online",
            shadow_out_logits=shadow_logits,
            keep_matrix=self._keep_matrix,
            shadow_in_means=shadow_in_means,
            shadow_out_means_online=shadow_out_means,
            target_logits=target_logits,
            lira_scores=lira_scores,
            lira_trues=lira_trues,
            class_labels=class_labels,
            sample_global_indices=sample_global_indices,
            train_size=train_size,
            test_size=test_size,
        )

        plot_score_distributions(
            model_save_dir=self.MODEL_SAVE_DIR,
            logger=self.logger,
            variant="online",
            lira_scores=lira_scores,
            lira_trues=lira_trues,
        )

        return lira_scores, lira_trues
