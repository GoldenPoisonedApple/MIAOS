from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.experiment_status import ExperimentStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.update_results_request_files import UpdateResultsRequestFiles
    from ..models.update_results_request_other_metrics import (
        UpdateResultsRequestOtherMetrics,
    )


T = TypeVar("T", bound="UpdateResultsRequest")


@_attrs_define
class UpdateResultsRequest:
    """実験の結果更新リクエスト

    Attributes:
        experiment_id (int): 実験ID
        files (UpdateResultsRequestFiles): その他のファイルのパス
        other_metrics (UpdateResultsRequestOtherMetrics): 拡張メトリクス
        status (ExperimentStatus):
        worker_name (str): 作業PC名
        error_message (None | str | Unset): エラーメッセージ
        global_auc (float | None | Unset): 全体のAUC
        threshold_at_01_fpr (float | None | Unset): 0.1%FPRでの閾値
        threshold_at_1_fpr (float | None | Unset): 1%FPRでの閾値
        total_time (float | None | Unset): トータルの実行時間(秒)
        tpr_at_01_fpr (float | None | Unset): 0.1%FPRでのTPR
        tpr_at_1_fpr (float | None | Unset): 1%FPRでのTPR
    """

    experiment_id: int
    files: UpdateResultsRequestFiles
    other_metrics: UpdateResultsRequestOtherMetrics
    status: ExperimentStatus
    worker_name: str
    error_message: None | str | Unset = UNSET
    global_auc: float | None | Unset = UNSET
    threshold_at_01_fpr: float | None | Unset = UNSET
    threshold_at_1_fpr: float | None | Unset = UNSET
    total_time: float | None | Unset = UNSET
    tpr_at_01_fpr: float | None | Unset = UNSET
    tpr_at_1_fpr: float | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        experiment_id = self.experiment_id

        files = self.files.to_dict()

        other_metrics = self.other_metrics.to_dict()

        status = self.status.value

        worker_name = self.worker_name

        error_message: None | str | Unset
        if isinstance(self.error_message, Unset):
            error_message = UNSET
        else:
            error_message = self.error_message

        global_auc: float | None | Unset
        if isinstance(self.global_auc, Unset):
            global_auc = UNSET
        else:
            global_auc = self.global_auc

        threshold_at_01_fpr: float | None | Unset
        if isinstance(self.threshold_at_01_fpr, Unset):
            threshold_at_01_fpr = UNSET
        else:
            threshold_at_01_fpr = self.threshold_at_01_fpr

        threshold_at_1_fpr: float | None | Unset
        if isinstance(self.threshold_at_1_fpr, Unset):
            threshold_at_1_fpr = UNSET
        else:
            threshold_at_1_fpr = self.threshold_at_1_fpr

        total_time: float | None | Unset
        if isinstance(self.total_time, Unset):
            total_time = UNSET
        else:
            total_time = self.total_time

        tpr_at_01_fpr: float | None | Unset
        if isinstance(self.tpr_at_01_fpr, Unset):
            tpr_at_01_fpr = UNSET
        else:
            tpr_at_01_fpr = self.tpr_at_01_fpr

        tpr_at_1_fpr: float | None | Unset
        if isinstance(self.tpr_at_1_fpr, Unset):
            tpr_at_1_fpr = UNSET
        else:
            tpr_at_1_fpr = self.tpr_at_1_fpr

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "experiment_id": experiment_id,
                "files": files,
                "other_metrics": other_metrics,
                "status": status,
                "worker_name": worker_name,
            }
        )
        if error_message is not UNSET:
            field_dict["error_message"] = error_message
        if global_auc is not UNSET:
            field_dict["global_auc"] = global_auc
        if threshold_at_01_fpr is not UNSET:
            field_dict["threshold_at_01_fpr"] = threshold_at_01_fpr
        if threshold_at_1_fpr is not UNSET:
            field_dict["threshold_at_1_fpr"] = threshold_at_1_fpr
        if total_time is not UNSET:
            field_dict["total_time"] = total_time
        if tpr_at_01_fpr is not UNSET:
            field_dict["tpr_at_01_fpr"] = tpr_at_01_fpr
        if tpr_at_1_fpr is not UNSET:
            field_dict["tpr_at_1_fpr"] = tpr_at_1_fpr

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.update_results_request_files import UpdateResultsRequestFiles
        from ..models.update_results_request_other_metrics import (
            UpdateResultsRequestOtherMetrics,
        )

        d = dict(src_dict)
        experiment_id = d.pop("experiment_id")

        files = UpdateResultsRequestFiles.from_dict(d.pop("files"))

        other_metrics = UpdateResultsRequestOtherMetrics.from_dict(
            d.pop("other_metrics")
        )

        status = ExperimentStatus(d.pop("status"))

        worker_name = d.pop("worker_name")

        def _parse_error_message(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error_message = _parse_error_message(d.pop("error_message", UNSET))

        def _parse_global_auc(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        global_auc = _parse_global_auc(d.pop("global_auc", UNSET))

        def _parse_threshold_at_01_fpr(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        threshold_at_01_fpr = _parse_threshold_at_01_fpr(
            d.pop("threshold_at_01_fpr", UNSET)
        )

        def _parse_threshold_at_1_fpr(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        threshold_at_1_fpr = _parse_threshold_at_1_fpr(
            d.pop("threshold_at_1_fpr", UNSET)
        )

        def _parse_total_time(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        total_time = _parse_total_time(d.pop("total_time", UNSET))

        def _parse_tpr_at_01_fpr(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        tpr_at_01_fpr = _parse_tpr_at_01_fpr(d.pop("tpr_at_01_fpr", UNSET))

        def _parse_tpr_at_1_fpr(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        tpr_at_1_fpr = _parse_tpr_at_1_fpr(d.pop("tpr_at_1_fpr", UNSET))

        update_results_request = cls(
            experiment_id=experiment_id,
            files=files,
            other_metrics=other_metrics,
            status=status,
            worker_name=worker_name,
            error_message=error_message,
            global_auc=global_auc,
            threshold_at_01_fpr=threshold_at_01_fpr,
            threshold_at_1_fpr=threshold_at_1_fpr,
            total_time=total_time,
            tpr_at_01_fpr=tpr_at_01_fpr,
            tpr_at_1_fpr=tpr_at_1_fpr,
        )

        update_results_request.additional_properties = d
        return update_results_request

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
