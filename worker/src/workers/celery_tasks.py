# celery_tasks.py の推奨例
import logging
import os
import tempfile
import time
from http import HTTPStatus

import torch
from celery import Celery

import src.core.config as cfg
from src.core.pipeline import run_experiment
import src.utils.minio_utils as minio_utils

from src.server_client import Client
from src.server_client.models import (
    CreateExperimentRequest,
    UpdateResultsRequest,
    UpdateResultsRequestFiles,
    UpdateResultsRequestOtherMetrics,
    ExperimentStatus,
    ClaimExperimentRequest,
)
from src.server_client.api.experiments import (
    reflect_experiment_results,
    claim_experiment,
)

logger = logging.getLogger(__name__)

# UpdateResultsRequest のトップレベルに載せる metrics キー（それ以外は other_metrics へ）
TOP_LEVEL_METRIC_KEYS = frozenset({
    "global_auc",
    "tpr_at_01_fpr",
    "tpr_at_1_fpr",
    "threshold_at_01_fpr",
    "threshold_at_1_fpr",
    "total_time_sec",
})


def _json_safe_metric_value(value):
    """API 送信用に metrics 値を JSON 直列化可能な型へ変換する。"""
    if value is None:
        return None
    if hasattr(value, "item") and callable(value.item):
        return value.item()
    if hasattr(value, "tolist") and callable(value.tolist):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_json_safe_metric_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe_metric_value(v) for k, v in value.items()}
    return value


def build_other_metrics(metrics: dict) -> UpdateResultsRequestOtherMetrics:
    """トップレベル以外の metrics を other_metrics として構築する。"""
    return UpdateResultsRequestOtherMetrics.from_dict({
        k: _json_safe_metric_value(v)
        for k, v in metrics.items()
        if k not in TOP_LEVEL_METRIC_KEYS and v is not None
    })


def _try_claim_experiment(client: Client, experiment_id: int) -> bool:
    """
    実験の claim を試みる。
    実行すべき場合は True、完了済み・他ワーカー実行中などでスキップすべき場合は False を返す。
    """
    payload = ClaimExperimentRequest(
        id=experiment_id,
        worker_name=cfg.PC_NAME,
    )
    response = claim_experiment.sync_detailed(client=client, body=payload)
    if response.status_code == HTTPStatus.OK:
        logger.info("Experiment %s claimed successfully", experiment_id)
        return True
    if response.status_code == HTTPStatus.CONFLICT:
        logger.warning("Experiment %s claim rejected (409), skipping", experiment_id)
        return False
    if response.status_code == HTTPStatus.NOT_FOUND:
        logger.error("Experiment %s not found", experiment_id)
        return False
    raise RuntimeError(
        f"claim failed for experiment {experiment_id}: HTTP {response.status_code}"
    )


def _try_reflect_results(client: Client, payload: UpdateResultsRequest) -> None:
    """実験結果を API に反映する。409 は既に反映済みとして正常終了する。"""
    response = reflect_experiment_results.sync_detailed(client=client, body=payload)
    if response.status_code == HTTPStatus.OK:
        logger.info(
            "Experiment %s results reflected successfully", payload.experiment_id
        )
        return
    if response.status_code == HTTPStatus.CONFLICT:
        logger.warning(
            "Experiment %s reflect rejected (409): results already applied, skipping",
            payload.experiment_id,
        )
        return
    if response.status_code == HTTPStatus.NOT_FOUND:
        logger.error("Experiment %s not found during reflect", payload.experiment_id)
        return
    raise RuntimeError(
        f"reflect failed for experiment {payload.experiment_id}: "
        f"HTTP {response.status_code}"
    )


def _release_gpu_memory() -> None:
    """長時間実行後の GPU メモリを解放する（ACK 前クラッシュのリスク低減）。"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


app = Celery("mia_tasks", broker=cfg._REDIS_URL)
# 全タスクのデフォルト値設定
app.conf.update(
    broker_transport_options={
        # これを超えるとRedisが「ワーカーが死んだ」と判断し再キューイングする。
        "visibility_timeout": cfg.CELERY_VISIBILITY_TIMEOUT,
    },
    task_acks_late=True,  # タスク完了後にACK brokerにタスクを残す
    task_reject_on_worker_lost=True,  # ワーカーが死んだ場合、タスクを再キューイングする
)


# メイン処理
# 送信処理以外を担う
def main(id: int, params) -> UpdateResultsRequest:
    try:
        # JSONからCreateExperimentRequestオブジェクトを復元
        request = CreateExperimentRequest.from_dict(params)

        # 依存モデルが存在する場合
        if request.base_experiment_id is not None:
            # ダウンロード
            # MinIOから落としてきたローカルの絶対パスを取得し、設定を上書きする
            assigned_model_path = minio_utils.download_model_dir(
                request.base_experiment_id
            )
        else:
            assigned_model_path = None

        # 他のPCのNASと衝突しないよう、一時ディレクトリを生成
        # ここにおける一時ディレクトリはコンテナ内の /tmp/ 配下に作成される
        # withを抜けると自動で削除される
        with tempfile.TemporaryDirectory(prefix="ito_research_") as temp_dir:
            # パイプライン実行 (結果は temp_dir に保存される)
            metrics = run_experiment(
                request,
                work_dir=temp_dir,
                assigned_model_path=assigned_model_path,
                experiment_id=id,
            )

            # OSのファイルシステム同期を確実に行うための待機
            time.sleep(2)

            # 実行結果アップロード
            remote_prefix = f"results/{id}/"
            minio_utils.upload_results_dir(temp_dir, remote_prefix=remote_prefix)

            # ------- MIAOS APIへの送信処理 -------
            # ファイル作成
            files_dict = {}
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    # temp_dirを起点とした相対パスを計算
                    rel_path = os.path.relpath(os.path.join(root, file), temp_dir)
                    minio_key = os.path.join(remote_prefix, rel_path).replace("\\", "/")
                    files_dict[rel_path] = minio_key
        # ペイロード作成
        payload = UpdateResultsRequest(
            experiment_id=id,
            files=UpdateResultsRequestFiles.from_dict(files_dict),
            global_auc=metrics.get("global_auc"),
            other_metrics=build_other_metrics(metrics),
            status=ExperimentStatus.SUCCEEDED,
            threshold_at_01_fpr=metrics.get("threshold_at_01_fpr"),
            threshold_at_1_fpr=metrics.get("threshold_at_1_fpr"),
            total_time=metrics.get("total_time_sec"),
            tpr_at_01_fpr=metrics.get("tpr_at_01_fpr"),
            tpr_at_1_fpr=metrics.get("tpr_at_1_fpr"),
            worker_name=cfg.PC_NAME,
            error_message=None,
        )
    except Exception as e:
        logger.exception("Experiment failed: %s", e)
        # ペイロード作成
        payload = UpdateResultsRequest(
            experiment_id=id,
            files=UpdateResultsRequestFiles.from_dict({}),
            global_auc=None,
            other_metrics=UpdateResultsRequestOtherMetrics.from_dict({}),
            status=ExperimentStatus.FAILED,
            threshold_at_01_fpr=None,
            threshold_at_1_fpr=None,
            total_time=None,
            tpr_at_01_fpr=None,
            tpr_at_1_fpr=None,
            worker_name=cfg.PC_NAME,
            error_message=str(e),
        )
    return payload


# タスクの取得、送信処理を担う
@app.task(
    name="mia_tasks.run_attack",
    acks_late=True,  # タスク完了後にACK
    reject_on_worker_lost=True,  # ワーカー異常終了時にrequeue
)
def execute_attack_task(_params):
    """
    _params: {"mia_method": "Shokri", "batch_size": 128, ...} のような辞書
    """
    # クライアントを作成
    client = Client(base_url=cfg._MIAOS_API_URL)

    # idを取得、削除
    id: int = _params.pop("experiment_id")

    # タスク取得報告（WAITING 以外は main をスキップして冪等に ACK）
    if not _try_claim_experiment(client, id):
        return

    try:
        # メイン処理
        payload = main(id, _params)
        _try_reflect_results(client, payload)
    finally:
        _release_gpu_memory()
