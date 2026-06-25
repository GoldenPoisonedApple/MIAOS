import torch
import torch.nn as nn
from tqdm import trange
import os
import logging
from abc import ABC, abstractmethod
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
from typing import Callable

# ROC曲線描画用に追加
import matplotlib

matplotlib.use("Agg")  # GUIを持たないDocker環境での描画用バックエンド
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc
import numpy as np

import src.core.config as cfg
from src.data.dataset import dataset
from src.server_client.models import CreateExperimentRequest


class MIA_Attack(ABC):
    def __init__(
        self,
        dataset: dataset,
        MODEL_SAVE_DIR: str,
        logger: logging.Logger,
        settings: CreateExperimentRequest,
    ):
        self.dataset = dataset
        self.MODEL_SAVE_DIR = MODEL_SAVE_DIR
        self.logger = logger
        self.settings = settings

    # ターゲットモデルの訓練、評価
    def train_target_model(self, target_model: nn.Module):
        """
        ターゲットモデルの訓練
        Args:
                target_model: ターゲットモデル
        Returns:
                target_model: 訓練後のターゲットモデル
        """
        # モデルをデバイスに転送
        target_model = target_model.to(cfg.DEVICE)
        # 訓練
        trainloader, testloader, num_train, num_test = (
            self.dataset.get_target_dataloaders()
        )  # データ読み込み
        self.logger.info(f"Train: {num_train}, Test: {num_test}")
        target_model = MIA_Attack.train_model(
            target_model, trainloader, self.settings.max_epochs
        )  # 訓練
        # モデルの保存
        torch.save(
            target_model.state_dict(),
            os.path.join(self.MODEL_SAVE_DIR, cfg.TARGET_MODEL_NAME),
        )

        train_acc = MIA_Attack.get_accuracy(
            target_model, trainloader
        )  # 訓練データに対する精度
        test_acc = MIA_Attack.get_accuracy(
            target_model, testloader
        )  # テストデータに対する精度
        self.logger.info(
            f"Target Result -> Train: {train_acc:.4f}, Test: {test_acc:.4f} (Gap: {train_acc - test_acc:.4f})"
        )

        return target_model

    # シャドーモデルの訓練、評価
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
        for i in trange(self.settings.num_shadow_models, desc="Shadow Models"):
            shadow_train_loader, shadow_test_loader, _, _ = (
                self.dataset.get_shadow_dataloader(seed=i)
            )
            # モデルを作成
            shadow_model = model_factory().to(cfg.DEVICE)
            # モデルを訓練
            shadow_model = MIA_Attack.train_model(
                shadow_model, shadow_train_loader, self.settings.max_epochs
            )
            shadow_model.to("cpu")  # GPUメモリ節約
            # リストを追加
            shadow_models.append(shadow_model)
            state_dicts.append(shadow_model.state_dict())
            # 評価
            # 未実装
        # モデルの保存
        torch.save(
            state_dicts, os.path.join(self.MODEL_SAVE_DIR, cfg.SHADOW_MODEL_NAME)
        )
        self.logger.info(
            f"Shadow Models saved -> {os.path.join(self.MODEL_SAVE_DIR, cfg.SHADOW_MODEL_NAME)}"
        )

        return shadow_models

    # 攻撃、評価
    @abstractmethod
    def attack(self, shadow_models: list[nn.Module]) -> tuple[np.ndarray, np.ndarray]:
        """
        攻撃、評価
        Args:
                shadow_models: シャドーモデル
        Returns:
                member_scores: np.ndarray 攻撃スコア(メンバー)
                member_trues: np.ndarray 真値ラベル(メンバー)
        """
        pass

    # モデルの総合評価
    def comprehensive_evaluate(self, scores: np.ndarray, trues: np.ndarray):

        # ------------- ROC曲線描画 -------------
        # thresholds: 閾値(閾値より大きい場合は1(陽性)と判断)
        fpr, tpr, thresholds = roc_curve(trues, scores)
        roc_auc = auc(fpr, tpr)

        plt.figure(figsize=(8, 8))
        plt.plot(
            fpr,
            tpr,
            color="green",
            lw=1,
            marker="o",
            markersize=3,
            label=f"Results (AUC = {roc_auc:.4f})",
        )
        plt.plot(
            [1e-5, 1],
            [1e-5, 1],
            color="navy",
            lw=2,
            linestyle="--",
            label="Random Guess",
        )
        plt.axvline(x=0.01, linestyle="--", linewidth=1, color="blue", label="1% FPR")
        plt.axvline(
            x=0.001, linestyle="--", linewidth=1, color="blue", label="0.1% FPR"
        )
        plt.axvline(
            x=0.0001, linestyle="--", linewidth=1, color="blue", label="0.01% FPR"
        )

        plt.xscale("log")
        plt.yscale("log")
        plt.xlim([1e-5, 1.0])
        plt.ylim([1e-5, 1.05])
        plt.xlabel("False Positive Rate (FPR)")
        plt.ylabel("True Positive Rate (TPR)")
        plt.title("Membership Inference Attack ROC Curve (Log-Log Scale)")
        plt.legend(loc="lower right")
        plt.grid(True, which="both", ls="--", alpha=0.5)
        # 保存
        roc_plot_path = os.path.join(self.MODEL_SAVE_DIR, "roc_curve.png")
        plt.savefig(roc_plot_path, dpi=300, bbox_inches="tight")
        plt.close()
        self.logger.info(f"Saved ROC curve plot to: {roc_plot_path}")

        # ------- 総合評価 -------
        self.logger.info("--- Results ---")
        self.logger.info(f"Global AUC: {roc_auc:.4f}")

        tpr_at_1_fpr, threshold_at_1_fpr = MIA_Attack.get_tpr_and_threshold(
            fpr, tpr, thresholds, 0.01
        )
        tpr_at_01_fpr, threshold_at_01_fpr = MIA_Attack.get_tpr_and_threshold(
            fpr, tpr, thresholds, 0.001
        )
        tpr_at_001_fpr, threshold_at_001_fpr = MIA_Attack.get_tpr_and_threshold(
            fpr, tpr, thresholds, 0.0001
        )

        self.logger.info(
            f"TPR: {(tpr_at_1_fpr * 100):.4f}% at 1.0% FPR, Threshold: {threshold_at_1_fpr:.4f}"
        )
        self.logger.info(
            f"TPR: {(tpr_at_01_fpr * 100):.4f}% at 0.1% FPR, Threshold: {threshold_at_01_fpr:.4f}"
        )
        self.logger.info(
            f"TPR: {(tpr_at_001_fpr * 100):.4f}% at 0.01% FPR, Threshold: {threshold_at_001_fpr:.4f}"
        )

        metrics = {
            "global_auc": float(roc_auc),
            "tpr_at_1_fpr": float(tpr_at_1_fpr),
            "tpr_at_01_fpr": float(tpr_at_01_fpr),
            "tpr_at_001_fpr": float(tpr_at_001_fpr),
            "threshold_at_1_fpr": float(threshold_at_1_fpr),
            "threshold_at_01_fpr": float(threshold_at_01_fpr),
            "threshold_at_001_fpr": float(threshold_at_001_fpr),
        }
        return metrics

    # ==========================================
    # 以下、Utility関数
    # ==========================================

    # モデルの訓練
    @staticmethod
    def train_model(model, train_loader, epochs):
        """
        モデルの訓練
        Args:
                model: モデル
                train_loader: 訓練データローダー
                epochs: エポック数
        Returns:
                model: 訓練後のモデル
        """
        # モデルの初期化
        model = model.to(cfg.DEVICE)
        # 損失関数とオプティマイザの定義
        criterion = nn.CrossEntropyLoss()
        # lr (Learning Rate): 学習率
        # weight_decay: L = 損失 + λ*重み: デカイ重みにペナルティ: 汎化性能向上
        optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
        # 学習率スケジューラ (CosineAnnealingLR: コサインカーブに従って学習率を減衰させる)
        # T_max: 半周期のエポック数 指定のエポック数で学習率(重みの修正幅)が最小値に達するように設定
        scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

        # 学習モード: Dropout(ランダムにニューロンを無効化)、BatchNorm(バッチごとの統計量を使用)
        model.train()
        for epoch in trange(epochs, desc="Epoch", leave=False):
            # バッチごとにデータを取得、ループ
            # i=0 input: (256, 3, 32, 32) labels: (256)
            # i=1 input: (256, 3, 32, 32) labels: (256)
            for inputs, labels in train_loader:
                # data: (labels, inputs)
                # to(device): データをGPUに転送
                # non_blocking=True: 非同期にデータ転送、pin_memory=Trueとの組み合わせ
                inputs, labels = (
                    inputs.to(cfg.DEVICE, non_blocking=True),
                    labels.to(cfg.DEVICE, non_blocking=True),
                )
                # 勾配の初期化
                optimizer.zero_grad()
                outputs = model(inputs)  # 順伝播
                loss = criterion(outputs, labels)  # 損失計算
                loss.backward()  # 逆伝播: 勾配を計算して各パラメータに保存
                optimizer.step()  # 重みの更新

            # エポックごとに学習率を更新
            scheduler.step()
        return model

    # 予測結果とラベルを取得
    @staticmethod
    def get_predictions(model, loader):
        """
        予測結果とラベルを取得
        Args:
                model: モデル
                loader: データローダー
        Returns:
                predictions: 予測結果確率(256*n, 100)
                例:
                tensor([
                                        [0.01, 0.00, 0.03, ..., 0.02],  # サンプル0
                                        [0.00, 0.01, 0.00, ..., 0.15],  # サンプル1
                                        [0.05, 0.00, 0.70, ..., 0.00],  # サンプル2
                                        [0.00, 0.00, 0.00, ..., 0.92],  # サンプル3
                                        [0.01, 0.00, 0.00, ..., 0.03],  # サンプル4
                                        [0.00, 0.02, 0.01, ..., 0.00],  # サンプル5
                                ])
                labels: 正解ラベル (256*n,)
                例: tensor([12, 45,  3, 99, 45, 17]) -> 一つ目のデータの正解ラベルは12
        """
        model = model.to(cfg.DEVICE)
        model.eval()  # 評価モード: 全結合、固定挙動
        preds = []
        labels_list = []
        with torch.no_grad():  # 評価時は勾配計算を無効化しメモリ消費を抑える
            for inputs, labels in loader:
                inputs = inputs.to(cfg.DEVICE, non_blocking=True)
                outputs = torch.softmax(model(inputs), dim=1)  # 出力を確率に変換
                preds.append(
                    outputs.cpu()
                )  # outputsはGPUにあるんで、確率はCPUに転送してリストに追加
                labels_list.append(labels)  # ラベルもリストに追加
        return torch.cat(preds), torch.cat(
            labels_list
        )  # 複数のテンソルを一つに結合 (256, 100)*n → (256*n, 100)

    # 精度を取得
    @staticmethod
    def get_accuracy(model, test_loader):
        """
        精度を取得
        Args:
                model: モデル
                test_loader: テストデータローダー
        Returns:
                accuracy: 精度
        """
        correct = 0
        total = 0
        model.eval()  # 評価モード: 全結合、固定挙動
        with torch.no_grad():  # 評価時は勾配計算を無効化しメモリ消費を抑える
            for inputs, labels in test_loader:
                inputs, labels = (
                    inputs.to(cfg.DEVICE, non_blocking=True),
                    labels.to(cfg.DEVICE, non_blocking=True),
                )
                outputs = model(inputs)  # 推論
                _, predicted = torch.max(
                    outputs.data, 1
                )  # 出力の最大値のインデックス取得
                # 正解数と総数を更新
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
        return correct / total

    # 特定のFPRにおけるTPRと閾値を取得
    @staticmethod
    def get_tpr_and_threshold(fpr, tpr, thresholds, target_fpr):
        """
        特定のFPRにおけるTPRと閾値を取得
        Args:
                fpr: FPR
                tpr: TPR
                thresholds: 閾値
                target_fpr: 特定のFPR
        Returns:
                tpr: TPR
                threshold: 閾値
        """
        mask = fpr <= target_fpr
        # 条件内でTrueがない場合は-1.0を返す
        if mask.sum() == 0:
            return 0.0, -1.0

        idx = tpr[
            mask
        ].argmax()  # 条件内で最大TPRの位置 [0.8, 0.9, 0.7, 0.6] → 0.9の位置=idx = 1
        selected_indices = np.where(mask)[
            0
        ]  # 条件内でTrueのインデックスを取得 [True, True, False, True] → [0, 1, 3]
        best_idx = selected_indices[
            idx
        ]  # 元のインデックスに戻す [0, 1, 3] → 1番目の = 1

        tpr_value = float(tpr[best_idx])
        threshold_value = float(thresholds[best_idx])
        # roc_curve の thresholds[0] は inf になり得る。JSON 送信不可のため -1.0 に正規化
        if not np.isfinite(threshold_value):
            threshold_value = -1.0
        if not np.isfinite(tpr_value):
            tpr_value = 0.0

        return tpr_value, threshold_value
