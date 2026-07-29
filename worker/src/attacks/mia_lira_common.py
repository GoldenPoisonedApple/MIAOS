import logging
import os
from typing import Literal

import matplotlib

matplotlib.use("Agg")  # GUIを持たないDocker環境での描画用バックエンド
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from tqdm import trange

from src.attacks.mia_attack import MIA_Attack
from src.data.dataset import dataset

LiraVariant = Literal["offline", "online"]


# 正規分布に変換
def logit_scaling(probs: torch.Tensor) -> torch.Tensor:
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
    probs = torch.clamp(probs, eps, 1.0 - eps) # 最小値: eps, 最大値: 1.0 - eps
    return torch.log(probs / (1.0 - probs))


# 正解クラスのロジットを抽出
def extract_correct_class_logits(
    model: nn.Module,
    train_loader,
    test_loader,
) -> tuple[np.ndarray, torch.Tensor, torch.Tensor]:
    """
    学習・テスト DataLoader から正解クラスのロジットを抽出する。
    Returns:
            logits: (train_size + test_size,)
            train_labels, test_labels: 各ローダーのラベル
    """
    preds_1, labels_1 = MIA_Attack.get_predictions(model, train_loader)
    preds_2, labels_2 = MIA_Attack.get_predictions(model, test_loader)
    # 正解クラスの予測確率抽出
    # preds_1[tensor([0,1,2]), tensor([1,0,2])]
    # -> [preds_1[0][1], preds_1[1][0], preds_1[2][2]]
    # -> [0.01, 0.00, 0.03]
    # 各サンプルの正解ラベルの予測確率が抽出される
    prob_1 = preds_1[torch.arange(len(labels_1)), labels_1]
    prob_2 = preds_2[torch.arange(len(labels_2)), labels_2]
    all_prob = torch.cat([prob_1, prob_2])
    # ロジット変換
    logits = logit_scaling(all_prob).numpy()
    return logits, labels_1, labels_2


# シャドーモデルからまとめてロジット行列を抽出
def extract_shadow_logits_matrix(
    shadow_models: list[nn.Module],
    train_loader,
    test_loader,
    num_shadow_models: int,
) -> np.ndarray:
    """
    全シャドーモデルからクエリサンプルごとのロジット行列を抽出する。
    Returns:
            shadow_logits: shape (num_shadows, num_samples)
    """
    shadow_logits = []
    for i in trange(
        num_shadow_models,
        desc="Feature Extraction with Shadow Models",
    ):
        logits, _, _ = extract_correct_class_logits(
            shadow_models[i], train_loader, test_loader
        )
        shadow_models[i].to("cpu")  # GPUメモリ節約
        shadow_logits.append(logits)
    return np.array(shadow_logits)


def plot_offline_sample_shadow_out_distribution(
    model_save_dir: str,
    logger: logging.Logger,
    dataset_obj: dataset,
    shadow_out_logits: np.ndarray,
    target_logits: np.ndarray,
    train_size: int,
    sample_idx: int,
) -> None:
    """1サンプル分の shadow OUT ロジット分布と、eval 装飾後画像を可視化する。"""
    sample_shadow_out_logits = shadow_out_logits[:, sample_idx] # サンプルのロジット群を取得
    sample_target_logit = target_logits[sample_idx] # サンプルのロジットを取得
    global_indices = np.concatenate(
        [dataset_obj.target_train_idx, dataset_obj.target_test_idx]
    )
    sample_global_index = int(global_indices[sample_idx]) # サンプルのインデックス取得
    sample_image, sample_label = dataset_obj.get_eval_decorated_sample(sample_idx)
    is_member = sample_idx < train_size # サンプルがメンバーかどうかを取得

    min_val = sample_shadow_out_logits.min()
    max_val = sample_shadow_out_logits.max()
    bins = np.linspace(min_val, max_val, 100)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(
        sample_shadow_out_logits,
        bins=bins,
        alpha=0.6,
        color="royalblue",
        label="Shadow Out Logits",
        density=True,
    )
    ax.axvline(
        sample_target_logit,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Target Logit ({sample_target_logit:.3f})",
    )
    ax.set_xlabel("Logits")
    ax.set_ylabel("Density")
    ax.set_title(
        f"Shadow OUT distribution (sample {sample_idx}, "
        f"{'member' if is_member else 'non-member'})"
    )
    ax.legend(loc="upper left")
    ax.grid(True, linestyle="--", alpha=0.5)

    ax_ins = ax.inset_axes([0.68, 0.52, 0.28, 0.40])
    ax_ins.imshow(sample_image, interpolation="nearest")
    ax_ins.set_xticks([])
    ax_ins.set_yticks([])
    ax_ins.set_title(
        f"idx={sample_global_index}\nlabel={sample_label}",
        fontsize=8,
        pad=2,
    )

    plot_path = os.path.join(
        model_save_dir, f"sample_shadow_out_dist_{sample_idx}.png"
    )
    fig.savefig(plot_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Saved sample shadow OUT distribution plot to: {plot_path}")


def plot_score_distributions(
    model_save_dir: str,
    logger: logging.Logger,
    variant: LiraVariant,
    lira_scores: np.ndarray,
    lira_trues: np.ndarray,
    z_scores: np.ndarray | None = None,
) -> None:
    """LiRA 攻撃スコアの分布を可視化する。"""
    variant_label = "Offline LiRA" if variant == "offline" else "Online LiRA"

    # ------------- 可視化 -------------
    if variant == "offline" and z_scores is not None:
        # z スコアの分布を可視化
        members_scores = z_scores[lira_trues == 1]
        non_members_scores = z_scores[lira_trues == 0]
        # スコアの最小値と最大値からビンの範囲を決定 (外れ値が大きすぎると見えなくなるためパーセンタイルでクリップ)
        min_val = np.percentile(z_scores, 0.1)
        max_val = np.percentile(z_scores, 99.9)
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
        plt.title(f"Distribution of Attack Scores ({variant_label})")
        plt.legend(loc="upper right")
        plt.grid(True, linestyle="--", alpha=0.5)
        # 保存
        dist_plot_path = os.path.join(model_save_dir, "score_distribution_lira.png")
        plt.savefig(dist_plot_path, dpi=300, bbox_inches="tight")
        plt.close()
        logger.info(f"Saved score distribution plot to: {dist_plot_path}")

    # 攻撃スコア（CDF または尤度比）の分布を可視化
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
    score_xlabel = (
        "Attack Score CDF (LiRA)"
        if variant == "offline"
        else "Attack Score (LiRA log-likelihood ratio)"
    )
    plt.xlabel(score_xlabel)
    plt.ylabel("Density")
    cdf_title = (
        f"Distribution of Attack Scores CDF ({variant_label})"
        if variant == "offline"
        else f"Distribution of Attack Scores ({variant_label})"
    )
    plt.title(cdf_title)
    plt.legend(loc="upper right")
    plt.grid(True, linestyle="--", alpha=0.5)
    # 保存
    cdf_filename = (
        "score_distribution_lira_cdf.png"
        if variant == "offline"
        else "score_distribution_lira.png"
    )
    dist_plot_path = os.path.join(model_save_dir, cdf_filename)
    plt.savefig(dist_plot_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved score distribution plot to: {dist_plot_path}")
