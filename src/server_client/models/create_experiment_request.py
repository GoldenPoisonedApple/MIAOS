from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..models.mia_method import MiaMethod
from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.create_experiment_request_hyperparameters import CreateExperimentRequestHyperparameters





T = TypeVar("T", bound="CreateExperimentRequest")



@_attrs_define
class CreateExperimentRequest:
    """ 実験の作成リクエスト

        Attributes:
            base_experiment_id (int | None | Unset): 既存実験結果を流用する実験結果
            batch_size (int | Unset): バッチサイズ Default: 256.
            hyperparameters (CreateExperimentRequestHyperparameters | Unset): その他のハイパーパラメータ
            load_attack_model (bool | Unset): 攻撃モデルを読み込むかどうか Default: False.
            load_shadow_model (bool | Unset): シャドウモデルを読み込むかどうか Default: False.
            load_target_model (bool | Unset): ターゲットモデルを読み込むかどうか Default: False.
            max_epochs (int | Unset): 最大エポック数 Default: 200.
            method (MiaMethod | Unset):  Default: MiaMethod.OFFLINELIRA.
            name (str | Unset): 実験名 Default: '2026-05-13_13-56-25'.
            notes (None | str | Unset): 備考
            num_shadow_models (int | Unset): シャドウモデル数 Default: 100.
            seed (int | Unset): シード値 Default: 42.
            shadow_test_size (int | Unset): シャドウモデルのテストサイズ Default: 10520.
            shadow_train_size (int | Unset): シャドウモデルのトレーニングサイズ Default: 10520.
            target_test_size (int | Unset): ターゲットモデルのテストサイズ Default: 10520.
            target_train_size (int | Unset): ターゲットモデルのトレーニングサイズ Default: 10520.
     """

    base_experiment_id: int | None | Unset = UNSET
    batch_size: int | Unset = 256
    hyperparameters: CreateExperimentRequestHyperparameters | Unset = UNSET
    load_attack_model: bool | Unset = False
    load_shadow_model: bool | Unset = False
    load_target_model: bool | Unset = False
    max_epochs: int | Unset = 200
    method: MiaMethod | Unset = MiaMethod.OFFLINELIRA
    name: str | Unset = '2026-05-13_13-56-25'
    notes: None | str | Unset = UNSET
    num_shadow_models: int | Unset = 100
    seed: int | Unset = 42
    shadow_test_size: int | Unset = 10520
    shadow_train_size: int | Unset = 10520
    target_test_size: int | Unset = 10520
    target_train_size: int | Unset = 10520
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        from ..models.create_experiment_request_hyperparameters import CreateExperimentRequestHyperparameters
        base_experiment_id: int | None | Unset
        if isinstance(self.base_experiment_id, Unset):
            base_experiment_id = UNSET
        else:
            base_experiment_id = self.base_experiment_id

        batch_size = self.batch_size

        hyperparameters: dict[str, Any] | Unset = UNSET
        if not isinstance(self.hyperparameters, Unset):
            hyperparameters = self.hyperparameters.to_dict()

        load_attack_model = self.load_attack_model

        load_shadow_model = self.load_shadow_model

        load_target_model = self.load_target_model

        max_epochs = self.max_epochs

        method: str | Unset = UNSET
        if not isinstance(self.method, Unset):
            method = self.method.value


        name = self.name

        notes: None | str | Unset
        if isinstance(self.notes, Unset):
            notes = UNSET
        else:
            notes = self.notes

        num_shadow_models = self.num_shadow_models

        seed = self.seed

        shadow_test_size = self.shadow_test_size

        shadow_train_size = self.shadow_train_size

        target_test_size = self.target_test_size

        target_train_size = self.target_train_size


        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({
        })
        if base_experiment_id is not UNSET:
            field_dict["base_experiment_id"] = base_experiment_id
        if batch_size is not UNSET:
            field_dict["batch_size"] = batch_size
        if hyperparameters is not UNSET:
            field_dict["hyperparameters"] = hyperparameters
        if load_attack_model is not UNSET:
            field_dict["load_attack_model"] = load_attack_model
        if load_shadow_model is not UNSET:
            field_dict["load_shadow_model"] = load_shadow_model
        if load_target_model is not UNSET:
            field_dict["load_target_model"] = load_target_model
        if max_epochs is not UNSET:
            field_dict["max_epochs"] = max_epochs
        if method is not UNSET:
            field_dict["method"] = method
        if name is not UNSET:
            field_dict["name"] = name
        if notes is not UNSET:
            field_dict["notes"] = notes
        if num_shadow_models is not UNSET:
            field_dict["num_shadow_models"] = num_shadow_models
        if seed is not UNSET:
            field_dict["seed"] = seed
        if shadow_test_size is not UNSET:
            field_dict["shadow_test_size"] = shadow_test_size
        if shadow_train_size is not UNSET:
            field_dict["shadow_train_size"] = shadow_train_size
        if target_test_size is not UNSET:
            field_dict["target_test_size"] = target_test_size
        if target_train_size is not UNSET:
            field_dict["target_train_size"] = target_train_size

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.create_experiment_request_hyperparameters import CreateExperimentRequestHyperparameters
        d = dict(src_dict)
        def _parse_base_experiment_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        base_experiment_id = _parse_base_experiment_id(d.pop("base_experiment_id", UNSET))


        batch_size = d.pop("batch_size", UNSET)

        _hyperparameters = d.pop("hyperparameters", UNSET)
        hyperparameters: CreateExperimentRequestHyperparameters | Unset
        if isinstance(_hyperparameters,  Unset):
            hyperparameters = UNSET
        else:
            hyperparameters = CreateExperimentRequestHyperparameters.from_dict(_hyperparameters)




        load_attack_model = d.pop("load_attack_model", UNSET)

        load_shadow_model = d.pop("load_shadow_model", UNSET)

        load_target_model = d.pop("load_target_model", UNSET)

        max_epochs = d.pop("max_epochs", UNSET)

        _method = d.pop("method", UNSET)
        method: MiaMethod | Unset
        if isinstance(_method,  Unset):
            method = UNSET
        else:
            method = MiaMethod(_method)




        name = d.pop("name", UNSET)

        def _parse_notes(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        notes = _parse_notes(d.pop("notes", UNSET))


        num_shadow_models = d.pop("num_shadow_models", UNSET)

        seed = d.pop("seed", UNSET)

        shadow_test_size = d.pop("shadow_test_size", UNSET)

        shadow_train_size = d.pop("shadow_train_size", UNSET)

        target_test_size = d.pop("target_test_size", UNSET)

        target_train_size = d.pop("target_train_size", UNSET)

        create_experiment_request = cls(
            base_experiment_id=base_experiment_id,
            batch_size=batch_size,
            hyperparameters=hyperparameters,
            load_attack_model=load_attack_model,
            load_shadow_model=load_shadow_model,
            load_target_model=load_target_model,
            max_epochs=max_epochs,
            method=method,
            name=name,
            notes=notes,
            num_shadow_models=num_shadow_models,
            seed=seed,
            shadow_test_size=shadow_test_size,
            shadow_train_size=shadow_train_size,
            target_test_size=target_test_size,
            target_train_size=target_train_size,
        )


        create_experiment_request.additional_properties = d
        return create_experiment_request

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
