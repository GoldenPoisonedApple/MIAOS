import numpy as np
import logging
from src.attacks.mia_attack import MIA_Attack
from src.data.dataset import dataset
import torch
import torch.nn as nn
from tqdm import trange
import src.core.config as cfg
import os
from src.server_client.models import CreateExperimentRequest
from src.models.attack_model import AttackNet


# 攻撃用のモデルを作成し、攻撃
class MIA_Shokri(MIA_Attack):
    def __init__(
        self,
        dataset: dataset,
        MODEL_SAVE_DIR: str,
        logger: logging.Logger,
        settings: CreateExperimentRequest,
    ):
        super().__init__(dataset, MODEL_SAVE_DIR, logger, settings)

    # MIA Attack
    def attack(
        self, shadow_models: list[nn.Module], target_model: nn.Module
    ) -> tuple[np.ndarray, np.ndarray]:

        # ------------- 特徴量抽出 -------------
        attack_x, attack_y, attack_classes = [], [], []
        for i in trange(
            self.settings.num_shadow_models,
            desc="Feature Extraction with Shadow Models",
        ):
            # 評価用のデータローダーを取得
            shadow_train_loader, shadow_test_loader, _, _ = (
                self.dataset.get_eval_shadow_dataloader(seed=i)
            )
            # 予測値の抽出
            in_preds, in_labels = MIA_Attack.get_predictions(
                shadow_models[i], shadow_train_loader
            )
            out_preds, out_labels = MIA_Attack.get_predictions(
                shadow_models[i], shadow_test_loader
            )
            shadow_models[i].to("cpu")  # GPUメモリ節約

            # 特徴量追加
            attack_x.append(in_preds.cpu())
            attack_x.append(out_preds.cpu())
            # ラベル追加
            attack_y.append(torch.ones(len(in_labels), dtype=torch.long))
            attack_y.append(torch.zeros(len(out_labels), dtype=torch.long))
            # クラス追加
            attack_classes.append(in_labels.cpu())
            attack_classes.append(out_labels.cpu())

        # 一つのテンソルに結合
        attack_x = torch.cat(attack_x)
        attack_y = torch.cat(attack_y)
        attack_classes = torch.cat(attack_classes)

        # ----------- 攻撃モデルの訓練 -------------
        # クラスごとに攻撃モデルを訓練
        attack_models = {}
        state_dicts = []
        for class_idx in trange(cfg.NUM_CLASSES, desc="Training Attack Models"):
            # クラスごとのマスクを作成
            class_mask = attack_classes == class_idx
            if class_mask.sum() == 0:  # クラスにデータがない場合はスキップ
                continue
            # データセット作成
            class_dataset = torch.utils.data.TensorDataset(
                attack_x[class_mask], attack_y[class_mask]
            )
            class_loader = torch.utils.data.DataLoader(
                class_dataset,
                batch_size=self.settings.batch_size,
                shuffle=True,
                num_workers=0,
                pin_memory=True,
            )
            # 攻撃モデルの訓練
            attack_model = AttackNet(input_dim=cfg.NUM_CLASSES).to(cfg.DEVICE)
            attack_model = MIA_Attack.train_model(
                attack_model, class_loader, cfg.ATTACK_MODEL_EPOCHS
            )
            # 追加
            attack_models[class_idx] = attack_model
            state_dicts.append(attack_model.state_dict())
        # 攻撃モデルの保存
        torch.save(
            state_dicts, os.path.join(self.MODEL_SAVE_DIR, cfg.ATTACK_MODEL_NAME)
        )
        self.logger.info(
            f"Attack Models saved -> {os.path.join(self.MODEL_SAVE_DIR, cfg.ATTACK_MODEL_NAME)}"
        )

        # ----------- 攻撃モデルの評価 -------------
        # ターゲットモデル
        target_train_loader, target_test_loader, _, _ = (
            self.dataset.get_eval_target_dataloaders()
        )
        target_in_preds, target_in_labels = MIA_Attack.get_predictions(
            target_model, target_train_loader
        )
        target_out_preds, target_out_labels = MIA_Attack.get_predictions(
            target_model, target_test_loader
        )

        # ROC用データの集約
        all_scores = []
        all_trues = []

        # クラスごとに評価
        for class_idx in trange(cfg.NUM_CLASSES, desc="Evaluating Classes"):
            # クラスに攻撃モデルがない場合はスキップ
            if class_idx not in attack_models:
                continue
            # クラスごとのマスクを作成
            class_mask_in = target_in_labels == class_idx
            class_mask_out = target_out_labels == class_idx
            # 抽出 Trueのやつだけ残す
            class_preds_in = target_in_preds[class_mask_in]
            class_preds_out = target_out_preds[class_mask_out]
            # データがない場合はスキップ
            if len(class_preds_in) == 0 or len(class_preds_out) == 0:
                continue

            # 攻撃モデルで予測
            with torch.no_grad():
                out_in = attack_models[class_idx](class_preds_in.to(cfg.DEVICE))
                out_out = attack_models[class_idx](class_preds_out.to(cfg.DEVICE))
                preds_in = out_in.cpu()
                preds_out = out_out.cpu()
                # クラス1(メンバー=In)の確率をSoftmaxで取得
                prob_in = torch.softmax(preds_in, dim=1)[:, 1].numpy()
                prob_out = torch.softmax(preds_out, dim=1)[:, 1].numpy()

            # ROC用データの集約
            all_scores.extend(prob_in)
            all_scores.extend(prob_out)
            all_trues.extend([1] * len(prob_in))
            all_trues.extend([0] * len(prob_out))

        # 結合
        all_scores = np.array(all_scores)
        all_trues = np.array(all_trues)

        return all_scores, all_trues
