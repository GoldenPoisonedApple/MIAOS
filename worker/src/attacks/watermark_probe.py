import json
import logging
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch.nn as nn
from scipy.spatial.distance import jensenshannon
from tqdm import trange

from src.attacks.mia_attack import MIA_Attack
from src.data.dataset import dataset
from src.server_client.models import CreateExperimentRequest


class WatermarkProbeAnalysis:
    """透かし画像1枚を probe として target / shadow の prediction 差を調べる"""

    def __init__(
        self,
        dataset: dataset,
        model_save_dir: str,
        logger: logging.Logger,
        settings: CreateExperimentRequest,
        variant: str = "on_black",
    ):
        self.dataset = dataset
        self.model_save_dir = model_save_dir
        self.logger = logger
        self.settings = settings
        self.variant = variant

    @staticmethod
    def _predict_probe(model: nn.Module, loader) -> np.ndarray:
        preds, _ = MIA_Attack.get_predictions(model, loader)
        return preds[0].numpy()

    def _analyze_one_probe(
        self,
        probe_loader,
        probe_name: str,
        shadow_models: list[nn.Module],
        target_model: nn.Module,
    ) -> dict:
        target_pred = self._predict_probe(target_model, probe_loader)

        shadow_preds = []
        for i in trange(
            len(shadow_models),
            desc=f"Watermark probe ({probe_name}) on shadow models",
        ):
            shadow_preds.append(self._predict_probe(shadow_models[i], probe_loader))
            shadow_models[i].to("cpu")

        shadow_preds = np.array(shadow_preds)
        shadow_mean = shadow_preds.mean(axis=0)
        shadow_std = shadow_preds.std(axis=0) + 1e-8

        delta = target_pred - shadow_mean
        z_per_class = delta / shadow_std

        return {
            "probe_name": probe_name,
            "target_pred": target_pred,
            "shadow_preds": shadow_preds,
            "shadow_mean": shadow_mean,
            "shadow_std": shadow_std,
            "delta": delta,
            "z_per_class": z_per_class,
            "metrics": {
                "target_top1_class": int(target_pred.argmax()),
                "target_top1_prob": float(target_pred.max()),
                "shadow_mean_top1_class": int(shadow_mean.argmax()),
                "shadow_mean_top1_prob": float(shadow_mean.max()),
                "top1_class_match": bool(target_pred.argmax() == shadow_mean.argmax()),
                "l2_delta": float(np.linalg.norm(delta)),
                "l1_delta": float(np.abs(delta).sum()),
                "max_abs_delta": float(np.abs(delta).max()),
                "max_abs_delta_class": int(np.abs(delta).argmax()),
                "js_divergence": float(jensenshannon(target_pred, shadow_mean) ** 2),
                "entropy_target": float(
                    -(target_pred * np.log(target_pred + 1e-12)).sum()
                ),
                "entropy_shadow_mean": float(
                    -(shadow_mean * np.log(shadow_mean + 1e-12)).sum()
                ),
            },
        }

    def analyze(
        self,
        shadow_models: list[nn.Module],
        target_model: nn.Module,
    ) -> dict:
        watermark_loader, variant = self.dataset.get_watermark_probe_dataloader(
            self.variant
        )
        watermark_result = self._analyze_one_probe(
            watermark_loader,
            probe_name=f"watermark_{variant}",
            shadow_models=shadow_models,
            target_model=target_model,
        )

        cifar_loader, cifar_global_idx, cifar_label = (
            self.dataset.get_cifar_probe_dataloader()
        )
        cifar_result = self._analyze_one_probe(
            cifar_loader,
            probe_name="cifar_control",
            shadow_models=shadow_models,
            target_model=target_model,
        )

        summary = {
            "variant": variant,
            "filter_id": self.dataset.watermark_config.filter_id,
            "watermark_probe": watermark_result["metrics"],
            "cifar_control_probe": {
                **cifar_result["metrics"],
                "global_idx": cifar_global_idx,
                "label": cifar_label,
            },
            "watermark_minus_cifar_l2_delta": float(
                np.linalg.norm(watermark_result["delta"] - cifar_result["delta"])
            ),
        }

        out_dir = self._save_artifacts(
            variant=variant,
            watermark_result=watermark_result,
            cifar_result=cifar_result,
            summary=summary,
        )
        self._plot_delta(
            watermark_result["delta"],
            title_prefix=f"watermark ({variant})",
            filename="delta_topk_watermark.png",
        )
        self._plot_delta(
            cifar_result["delta"],
            title_prefix="cifar control",
            filename="delta_topk_cifar_control.png",
        )
        self._plot_predictions(
            watermark_result["target_pred"],
            watermark_result["shadow_mean"],
            title="Watermark probe: top-k class probabilities",
            filename="pred_topk_watermark.png",
        )
        self._plot_predictions(
            cifar_result["target_pred"],
            cifar_result["shadow_mean"],
            title="CIFAR control probe: top-k class probabilities",
            filename="pred_topk_cifar_control.png",
        )

        self.logger.info("Watermark probe saved to: %s", out_dir)
        self.logger.info("Watermark probe summary: %s", summary)
        return summary

    def _save_artifacts(
        self,
        variant: str,
        watermark_result: dict,
        cifar_result: dict,
        summary: dict,
    ) -> str:
        out_dir = os.path.join(self.model_save_dir, "watermark_probe")
        os.makedirs(out_dir, exist_ok=True)

        np.savez_compressed(
            os.path.join(out_dir, "watermark_probe_artifacts.npz"),
            variant=variant,
            watermark_target_pred=watermark_result["target_pred"],
            watermark_shadow_preds=watermark_result["shadow_preds"],
            watermark_shadow_mean=watermark_result["shadow_mean"],
            watermark_shadow_std=watermark_result["shadow_std"],
            watermark_delta=watermark_result["delta"],
            watermark_z_per_class=watermark_result["z_per_class"],
            cifar_target_pred=cifar_result["target_pred"],
            cifar_shadow_preds=cifar_result["shadow_preds"],
            cifar_shadow_mean=cifar_result["shadow_mean"],
            cifar_shadow_std=cifar_result["shadow_std"],
            cifar_delta=cifar_result["delta"],
            cifar_z_per_class=cifar_result["z_per_class"],
        )

        with open(
            os.path.join(out_dir, "watermark_probe_metrics.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return out_dir

    def _plot_delta(self, delta: np.ndarray, title_prefix: str, filename: str) -> None:
        topk = 20
        idx = np.argsort(np.abs(delta))[-topk:][::-1]

        plt.figure(figsize=(10, 5))
        plt.bar(range(topk), delta[idx])
        plt.xticks(range(topk), idx, rotation=45)
        plt.axhline(0, color="black", linewidth=0.8)
        plt.title(f"Target - ShadowMean prediction delta ({title_prefix}, top {topk})")
        plt.xlabel("Class ID")
        plt.ylabel("Delta probability")
        plt.tight_layout()
        plt.savefig(
            os.path.join(self.model_save_dir, "watermark_probe", filename),
            dpi=200,
        )
        plt.close()

    def _plot_predictions(
        self,
        target_pred: np.ndarray,
        shadow_mean: np.ndarray,
        title: str,
        filename: str,
    ) -> None:
        topk = 10
        idx = np.argsort(target_pred)[-topk:][::-1]

        x = np.arange(topk)
        width = 0.35
        plt.figure(figsize=(10, 5))
        plt.bar(x - width / 2, target_pred[idx], width, label="Target")
        plt.bar(x + width / 2, shadow_mean[idx], width, label="Shadow mean")
        plt.xticks(x, idx)
        plt.legend()
        plt.title(title)
        plt.tight_layout()
        plt.savefig(
            os.path.join(self.model_save_dir, "watermark_probe", filename),
            dpi=200,
        )
        plt.close()
