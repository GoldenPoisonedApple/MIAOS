from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.experiment_status import ExperimentStatus
from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.update_results_request_files import UpdateResultsRequestFiles
  from ..models.update_results_request_other_metrics import UpdateResultsRequestOtherMetrics





T = TypeVar("T", bound="UpdateResultsRequest")



@_attrs_define
class UpdateResultsRequest:
    """ 実験の結果更新リクエスト

        Attributes:
            experiment_id (int): 実験ID
            files (UpdateResultsRequestFiles): その他のファイルのパス
            global_auc (float): 全体のAUC
            other_metrics (UpdateResultsRequestOtherMetrics): 拡張メトリクス
            status (ExperimentStatus):
            threshold_at_01_fpr (float): 0.1%FPRでの閾値
            threshold_at_1_fpr (float): 1%FPRでの閾値
            total_time (float): トータルの実行時間(秒)
            tpr_at_01_fpr (float): 0.1%FPRでのTPR
            tpr_at_1_fpr (float): 1%FPRでのTPR
            worker_name (str): 作業PC名
            error_message (None | str | Unset): エラーメッセージ
     """

    experiment_id: int
    files: UpdateResultsRequestFiles
    global_auc: float
    other_metrics: UpdateResultsRequestOtherMetrics
    status: ExperimentStatus
    threshold_at_01_fpr: float
    threshold_at_1_fpr: float
    total_time: float
    tpr_at_01_fpr: float
    tpr_at_1_fpr: float
    worker_name: str
    error_message: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        from ..models.update_results_request_files import UpdateResultsRequestFiles
        from ..models.update_results_request_other_metrics import UpdateResultsRequestOtherMetrics
        experiment_id = self.experiment_id

        files = self.files.to_dict()

        global_auc = self.global_auc

        other_metrics = self.other_metrics.to_dict()

        status = self.status.value

        threshold_at_01_fpr = self.threshold_at_01_fpr

        threshold_at_1_fpr = self.threshold_at_1_fpr

        total_time = self.total_time

        tpr_at_01_fpr = self.tpr_at_01_fpr

        tpr_at_1_fpr = self.tpr_at_1_fpr

        worker_name = self.worker_name

        error_message: None | str | Unset
        if isinstance(self.error_message, Unset):
            error_message = UNSET
        else:
            error_message = self.error_message


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
            "experiment_id": experiment_id,
            "files": files,
            "global_auc": global_auc,
            "other_metrics": other_metrics,
            "status": status,
            "threshold_at_01_fpr": threshold_at_01_fpr,
            "threshold_at_1_fpr": threshold_at_1_fpr,
            "total_time": total_time,
            "tpr_at_01_fpr": tpr_at_01_fpr,
            "tpr_at_1_fpr": tpr_at_1_fpr,
            "worker_name": worker_name,
        })
        if error_message is not UNSET:
            field_dict["error_message"] = error_message

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.update_results_request_files import UpdateResultsRequestFiles
        from ..models.update_results_request_other_metrics import UpdateResultsRequestOtherMetrics
        d = dict(src_dict)
        experiment_id = d.pop("experiment_id")

        files = UpdateResultsRequestFiles.from_dict(d.pop("files"))




        global_auc = d.pop("global_auc")

        other_metrics = UpdateResultsRequestOtherMetrics.from_dict(d.pop("other_metrics"))




        status = ExperimentStatus(d.pop("status"))




        threshold_at_01_fpr = d.pop("threshold_at_01_fpr")

        threshold_at_1_fpr = d.pop("threshold_at_1_fpr")

        total_time = d.pop("total_time")

        tpr_at_01_fpr = d.pop("tpr_at_01_fpr")

        tpr_at_1_fpr = d.pop("tpr_at_1_fpr")

        worker_name = d.pop("worker_name")

        def _parse_error_message(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error_message = _parse_error_message(d.pop("error_message", UNSET))


        update_results_request = cls(
            experiment_id=experiment_id,
            files=files,
            global_auc=global_auc,
            other_metrics=other_metrics,
            status=status,
            threshold_at_01_fpr=threshold_at_01_fpr,
            threshold_at_1_fpr=threshold_at_1_fpr,
            total_time=total_time,
            tpr_at_01_fpr=tpr_at_01_fpr,
            tpr_at_1_fpr=tpr_at_1_fpr,
            worker_name=worker_name,
            error_message=error_message,
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
