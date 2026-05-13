from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..models.experiment_status import ExperimentStatus
from ..models.mia_method import MiaMethod
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.model_files_type_0 import ModelFilesType0
    from ..models.model_hyperparameters import ModelHyperparameters
    from ..models.model_other_metrics_type_0 import ModelOtherMetricsType0


T = TypeVar("T", bound="Model")


@_attrs_define
class Model:
    """
    Attributes:
        batch_size (int): バッチサイズ
        created_at (datetime.datetime): 作成日時
        hyperparameters (ModelHyperparameters): その他のハイパーパラメータ
        id (int): 主キー
        load_attack_model (bool): 攻撃モデルを読み込むかどうか
        load_shadow_model (bool): シャドウモデルを読み込むかどうか
        load_target_model (bool): ターゲットモデルを読み込むかどうか
        max_epochs (int): 最大エポック数
        method (MiaMethod):
        name (str): 実験名
        num_shadow_models (int): シャドウモデル数
        seed (int): シード値
        shadow_test_size (int): シャドウモデルのテストサイズ
        shadow_train_size (int): シャドウモデルのトレーニングサイズ
        status (ExperimentStatus):
        target_test_size (int): ターゲットモデルのテストサイズ
        target_train_size (int): ターゲットモデルのトレーニングサイズ
        base_experiment_id (int | None | Unset): 既存実験結果を流用する実験結果
        completed_at (datetime.datetime | None | Unset): 完了日時
        error_message (None | str | Unset): エラーメッセージ
        files (ModelFilesType0 | None | Unset):
        global_auc (float | None | Unset): 全体のAUC
        notes (None | str | Unset): 備考
        other_metrics (ModelOtherMetricsType0 | None | Unset): その他のメトリクス
        threshold_at_01_fpr (float | None | Unset): 0.1%FPRでの閾値
        threshold_at_1_fpr (float | None | Unset): 1%FPRでの閾値
        total_time (float | None | Unset): トータルの実行時間(秒)
        tpr_at_01_fpr (float | None | Unset): 0.1%FPRでのTPR
        tpr_at_1_fpr (float | None | Unset): 1%FPRでのTPR
        worker_name (None | str | Unset): 作業PC名
    """

    batch_size: int
    created_at: datetime.datetime
    hyperparameters: ModelHyperparameters
    id: int
    load_attack_model: bool
    load_shadow_model: bool
    load_target_model: bool
    max_epochs: int
    method: MiaMethod
    name: str
    num_shadow_models: int
    seed: int
    shadow_test_size: int
    shadow_train_size: int
    status: ExperimentStatus
    target_test_size: int
    target_train_size: int
    base_experiment_id: int | None | Unset = UNSET
    completed_at: datetime.datetime | None | Unset = UNSET
    error_message: None | str | Unset = UNSET
    files: ModelFilesType0 | None | Unset = UNSET
    global_auc: float | None | Unset = UNSET
    notes: None | str | Unset = UNSET
    other_metrics: ModelOtherMetricsType0 | None | Unset = UNSET
    threshold_at_01_fpr: float | None | Unset = UNSET
    threshold_at_1_fpr: float | None | Unset = UNSET
    total_time: float | None | Unset = UNSET
    tpr_at_01_fpr: float | None | Unset = UNSET
    tpr_at_1_fpr: float | None | Unset = UNSET
    worker_name: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.model_files_type_0 import ModelFilesType0
        from ..models.model_other_metrics_type_0 import ModelOtherMetricsType0

        batch_size = self.batch_size

        created_at = self.created_at.isoformat()

        hyperparameters = self.hyperparameters.to_dict()

        id = self.id

        load_attack_model = self.load_attack_model

        load_shadow_model = self.load_shadow_model

        load_target_model = self.load_target_model

        max_epochs = self.max_epochs

        method = self.method.value

        name = self.name

        num_shadow_models = self.num_shadow_models

        seed = self.seed

        shadow_test_size = self.shadow_test_size

        shadow_train_size = self.shadow_train_size

        status = self.status.value

        target_test_size = self.target_test_size

        target_train_size = self.target_train_size

        base_experiment_id: int | None | Unset
        if isinstance(self.base_experiment_id, Unset):
            base_experiment_id = UNSET
        else:
            base_experiment_id = self.base_experiment_id

        completed_at: None | str | Unset
        if isinstance(self.completed_at, Unset):
            completed_at = UNSET
        elif isinstance(self.completed_at, datetime.datetime):
            completed_at = self.completed_at.isoformat()
        else:
            completed_at = self.completed_at

        error_message: None | str | Unset
        if isinstance(self.error_message, Unset):
            error_message = UNSET
        else:
            error_message = self.error_message

        files: dict[str, Any] | None | Unset
        if isinstance(self.files, Unset):
            files = UNSET
        elif isinstance(self.files, ModelFilesType0):
            files = self.files.to_dict()
        else:
            files = self.files

        global_auc: float | None | Unset
        if isinstance(self.global_auc, Unset):
            global_auc = UNSET
        else:
            global_auc = self.global_auc

        notes: None | str | Unset
        if isinstance(self.notes, Unset):
            notes = UNSET
        else:
            notes = self.notes

        other_metrics: dict[str, Any] | None | Unset
        if isinstance(self.other_metrics, Unset):
            other_metrics = UNSET
        elif isinstance(self.other_metrics, ModelOtherMetricsType0):
            other_metrics = self.other_metrics.to_dict()
        else:
            other_metrics = self.other_metrics

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

        worker_name: None | str | Unset
        if isinstance(self.worker_name, Unset):
            worker_name = UNSET
        else:
            worker_name = self.worker_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "batch_size": batch_size,
                "created_at": created_at,
                "hyperparameters": hyperparameters,
                "id": id,
                "load_attack_model": load_attack_model,
                "load_shadow_model": load_shadow_model,
                "load_target_model": load_target_model,
                "max_epochs": max_epochs,
                "method": method,
                "name": name,
                "num_shadow_models": num_shadow_models,
                "seed": seed,
                "shadow_test_size": shadow_test_size,
                "shadow_train_size": shadow_train_size,
                "status": status,
                "target_test_size": target_test_size,
                "target_train_size": target_train_size,
            }
        )
        if base_experiment_id is not UNSET:
            field_dict["base_experiment_id"] = base_experiment_id
        if completed_at is not UNSET:
            field_dict["completed_at"] = completed_at
        if error_message is not UNSET:
            field_dict["error_message"] = error_message
        if files is not UNSET:
            field_dict["files"] = files
        if global_auc is not UNSET:
            field_dict["global_auc"] = global_auc
        if notes is not UNSET:
            field_dict["notes"] = notes
        if other_metrics is not UNSET:
            field_dict["other_metrics"] = other_metrics
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
        if worker_name is not UNSET:
            field_dict["worker_name"] = worker_name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.model_files_type_0 import ModelFilesType0
        from ..models.model_hyperparameters import ModelHyperparameters
        from ..models.model_other_metrics_type_0 import ModelOtherMetricsType0

        d = dict(src_dict)
        batch_size = d.pop("batch_size")

        created_at = isoparse(d.pop("created_at"))

        hyperparameters = ModelHyperparameters.from_dict(d.pop("hyperparameters"))

        id = d.pop("id")

        load_attack_model = d.pop("load_attack_model")

        load_shadow_model = d.pop("load_shadow_model")

        load_target_model = d.pop("load_target_model")

        max_epochs = d.pop("max_epochs")

        method = MiaMethod(d.pop("method"))

        name = d.pop("name")

        num_shadow_models = d.pop("num_shadow_models")

        seed = d.pop("seed")

        shadow_test_size = d.pop("shadow_test_size")

        shadow_train_size = d.pop("shadow_train_size")

        status = ExperimentStatus(d.pop("status"))

        target_test_size = d.pop("target_test_size")

        target_train_size = d.pop("target_train_size")

        def _parse_base_experiment_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        base_experiment_id = _parse_base_experiment_id(
            d.pop("base_experiment_id", UNSET)
        )

        def _parse_completed_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                completed_at_type_0 = isoparse(data)

                return completed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        completed_at = _parse_completed_at(d.pop("completed_at", UNSET))

        def _parse_error_message(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error_message = _parse_error_message(d.pop("error_message", UNSET))

        def _parse_files(data: object) -> ModelFilesType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                files_type_0 = ModelFilesType0.from_dict(data)

                return files_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ModelFilesType0 | None | Unset, data)

        files = _parse_files(d.pop("files", UNSET))

        def _parse_global_auc(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        global_auc = _parse_global_auc(d.pop("global_auc", UNSET))

        def _parse_notes(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        notes = _parse_notes(d.pop("notes", UNSET))

        def _parse_other_metrics(data: object) -> ModelOtherMetricsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                other_metrics_type_0 = ModelOtherMetricsType0.from_dict(data)

                return other_metrics_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ModelOtherMetricsType0 | None | Unset, data)

        other_metrics = _parse_other_metrics(d.pop("other_metrics", UNSET))

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

        def _parse_worker_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        worker_name = _parse_worker_name(d.pop("worker_name", UNSET))

        model = cls(
            batch_size=batch_size,
            created_at=created_at,
            hyperparameters=hyperparameters,
            id=id,
            load_attack_model=load_attack_model,
            load_shadow_model=load_shadow_model,
            load_target_model=load_target_model,
            max_epochs=max_epochs,
            method=method,
            name=name,
            num_shadow_models=num_shadow_models,
            seed=seed,
            shadow_test_size=shadow_test_size,
            shadow_train_size=shadow_train_size,
            status=status,
            target_test_size=target_test_size,
            target_train_size=target_train_size,
            base_experiment_id=base_experiment_id,
            completed_at=completed_at,
            error_message=error_message,
            files=files,
            global_auc=global_auc,
            notes=notes,
            other_metrics=other_metrics,
            threshold_at_01_fpr=threshold_at_01_fpr,
            threshold_at_1_fpr=threshold_at_1_fpr,
            total_time=total_time,
            tpr_at_01_fpr=tpr_at_01_fpr,
            tpr_at_1_fpr=tpr_at_1_fpr,
            worker_name=worker_name,
        )

        model.additional_properties = d
        return model

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
