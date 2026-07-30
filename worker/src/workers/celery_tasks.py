# celery_tasks.py の推奨例
import logging
import os
import tempfile
import time

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

    # タスク取得報告
    payload = ClaimExperimentRequest(
        id=id,
        worker_name=cfg.PC_NAME,
    )
    try:
        response = claim_experiment.sync(client=client, body=payload)
        print(f"MIAOS APIへの送信成功: {response}")
    except Exception as e:
        print(f"MIAOS APIへの送信失敗: {e}")

    # メイン処理
    payload = main(id, _params)

    try:
        response = reflect_experiment_results.sync(client=client, body=payload)
        print(f"MIAOS APIへの送信成功: {response}")
    except Exception as e:
        print(f"MIAOS APIへの送信失敗: {e}")
