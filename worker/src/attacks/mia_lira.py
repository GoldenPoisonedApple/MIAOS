import numpy as np
import logging
from src.attacks.mia_attack import MIA_Attack
from src.data.dataset import dataset
import torch
import torch.nn as nn
from tqdm import trange
from scipy.stats import norm
from src.server_client.models import CreateExperimentRequest

# ROC曲線描画用に追加
import matplotlib

matplotlib.use("Agg")  # GUIを持たないDocker環境での描画用バックエンド
import matplotlib.pyplot as plt
import os


# 最尤度攻撃(LiRA)
class MIA_LIRA(MIA_Attack):
    def __init__(
        self,
        dataset: dataset,
        MODEL_SAVE_DIR: str,
        logger: logging.Logger,
        settings: CreateExperimentRequest,
    ):
        super().__init__(dataset, MODEL_SAVE_DIR, logger, settings)

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

    # Offline LiRA の再現用アーティファクトを保存
    def _save_lira_artifacts(
        self,
        shadow_out_logits: np.ndarray,
        shadow_out_means: np.ndarray,
        shadow_out_stds: np.ndarray,
        target_logits: np.ndarray,
        z_scores: np.ndarray,
        lira_scores: np.ndarray,
        lira_trues: np.ndarray,
        class_labels: np.ndarray,
        sample_global_indices: np.ndarray,
        train_size: int,
        test_size: int,
    ) -> str:
        """
        OUT 分布・z スコア・LiRA スコアをファイルに保存する。
        Returns:
                保存先ディレクトリのパス
        """
        artifacts_dir = os.path.join(self.MODEL_SAVE_DIR, "lira_artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)

        npz_path = os.path.join(artifacts_dir, "lira_artifacts.npz")
        np.savez_compressed(
            npz_path,
            # シャドウ OUT 分布: shape (num_shadows, num_samples)
            shadow_out_logits=shadow_out_logits,
            shadow_out_means=shadow_out_means,
            shadow_out_stds=shadow_out_stds,
            # ターゲット観測と攻撃スコア: shape (num_samples,)
            target_logits=target_logits,
            z_scores=z_scores,
            lira_scores=lira_scores,
            # ラベル・識別子
            membership_labels=lira_trues,
            class_labels=class_labels,
            sample_global_indices=sample_global_indices,
            train_size=np.array(train_size),
            test_size=np.array(test_size),
        )

        self.logger.info(f"Saved LiRA artifacts to: {artifacts_dir}")
        return artifacts_dir

    # LiRA Attack
    # Offline LiRA
    def attack(
        self, shadow_models: list[nn.Module], target_model: nn.Module
    ) -> tuple[np.ndarray, np.ndarray]:

        # ターゲットモデルの学習データとテストデータを取得 検証用
        target_train_loader, target_test_loader, train_size, test_size = (
            self.dataset.get_eval_target_dataloaders()
        )

        # ------------- 特徴量抽出 -------------
        # ターゲットデータを学習に使用しなかったモデルを選び出し、Out分布を推定(targetのデータはshadowモデルで一切学習していないため使用可能)
        # -------------------------------------
        shadow_out_logits = []
        for i in trange(
            self.settings.num_shadow_models,
            desc="Feature Extraction with Shadow Models",
        ):
            # 予測値の抽出
            preds_1, labels_1 = MIA_Attack.get_predictions(
                shadow_models[i], target_train_loader
            )
            preds_2, labels_2 = MIA_Attack.get_predictions(
                shadow_models[i], target_test_loader
            )
            shadow_models[i].to("cpu")  # GPUメモリ節約

            # 正解クラスの予測確率抽出
            # preds_1[tensor([0,1,2]), tensor([1,0,2])]
            # -> [preds_1[0][1], preds_1[1][0], preds_1[2][2]]
            # -> [0.01, 0.00, 0.03]
            # 各サンプルの正解ラベルの予測確率が抽出される
            prob_1 = preds_1[torch.arange(len(labels_1)), labels_1]
            prob_2 = preds_2[torch.arange(len(labels_2)), labels_2]
            all_prob = torch.cat([prob_1, prob_2])
            # ロジット変換
            logits = MIA_LIRA.logit_scaling(all_prob).numpy()
            # リストに追加
            shadow_out_logits.append(logits)

        # リストをNumpy配列に変換
        shadow_out_logits = np.array(shadow_out_logits)
        # シャドーモデル群から、サンプルごとの平均と標準偏差を計算
        # axis=0: 列方向 サンプルごとの平均と標準偏差を計算
        shadow_out_means = np.mean(shadow_out_logits, axis=0)
        shadow_out_stds = np.std(shadow_out_logits, axis=0) + 1e-8  # ゼロ除算防止

        # ------- 攻撃スコア計算 ---------------
        # ターゲットモデルから、同じ検証したいデータのロジットを抽出
        # -------------------------------------
        preds_1, labels_1 = MIA_Attack.get_predictions(
            target_model, target_train_loader
        )
        preds_2, labels_2 = MIA_Attack.get_predictions(target_model, target_test_loader)
        # 正解クラスの確率抽出
        prob_1 = preds_1[torch.arange(len(labels_1)), labels_1]
        prob_2 = preds_2[torch.arange(len(labels_2)), labels_2]
        target_prob = torch.cat([prob_1, prob_2])
        # ロジット変換
        target_logits = MIA_LIRA.logit_scaling(target_prob).numpy()

        # -------------------------------------
        # 攻撃スコア計算
        # Λ = Pr[Z <= conf_obs] = Φ((conf_obs - μ_out) / σ_out)
        # スコアが μ_outより極端に高い -> 非メンバーである確率は低い → メンバーである可能性が高い
        # -------------------------------------
        z_scores = (target_logits - shadow_out_means) / shadow_out_stds
        # zスコアから累積確率を計算
        # → 非メンバーの分布の lira_scores%より離れている -> メンバーである可能性が高い
        lira_scores = norm.cdf(z_scores)

        lira_trues = np.concatenate([np.ones(train_size), np.zeros(test_size)])
        class_labels = torch.cat([labels_1, labels_2]).numpy()
        sample_global_indices = np.concatenate(
            [self.dataset.target_train_idx, self.dataset.target_test_idx]
        )

        self._save_lira_artifacts(
            shadow_out_logits=shadow_out_logits,
            shadow_out_means=shadow_out_means,
            shadow_out_stds=shadow_out_stds,
            target_logits=target_logits,
            z_scores=z_scores,
            lira_scores=lira_scores,
            lira_trues=lira_trues,
            class_labels=class_labels,
            sample_global_indices=sample_global_indices,
            train_size=train_size,
            test_size=test_size,
        )

        # ------------- 可視化 -------------
        members_scores = lira_scores[lira_trues == 1]
        non_members_scores = lira_scores[lira_trues == 0]
        # スコアの最小値と最大値からビンの範囲を決定 (外れ値が大きすぎると見えなくなるためパーセンタイルでクリップ)
        min_val = np.percentile(lira_scores, 0.1)
        max_val = np.percentile(lira_scores, 99.9)
        bins = np.linspace(min_val, max_val, 100)
        # 密度(density=True)としてプロットし、2つの分布を比較しやすくする
        plt.figure(figsize=(10, 6))
        plt.hist(
            members_scores,
            bins=bins,
            alpha=0.6,
            color="royalblue",
            label="Members",
            density=True,
        )
        plt.hist(
            non_members_scores,
            bins=bins,
            alpha=0.6,
            color="crimson",
            label="Non-Members",
            density=True,
        )
        # 情報追加
        plt.xlabel("Attack Score (LiRA)")
        plt.ylabel("Density")
        plt.title("Distribution of Attack Scores (Offline LiRA)")
        plt.legend(loc="upper right")
        plt.grid(True, linestyle="--", alpha=0.5)
        # 保存
        dist_plot_path = os.path.join(
            self.MODEL_SAVE_DIR, "score_distribution_lira.png"
        )
        plt.savefig(dist_plot_path, dpi=300, bbox_inches="tight")
        plt.close()
        self.logger.info(f"Saved score distribution plot to: {dist_plot_path}")

        return lira_scores, lira_trues
