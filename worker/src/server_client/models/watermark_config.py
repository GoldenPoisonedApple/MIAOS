from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.watermark_config_apply import WatermarkConfigApply


T = TypeVar("T", bound="WatermarkConfig")


@_attrs_define
class WatermarkConfig:
    """透かし設定（`experiments.watermark` JSONB）

    Attributes:
        apply (WatermarkConfigApply | Unset): 分割名 → 適用割合（0.0〜1.0）
        enabled (bool | Unset): 透かしを有効にするか
        filter_id (None | str | Unset): MinIO フィルタ ID（`filters/{id}.png`）
        seed_offset (int | Unset): シードオフセット
    """

    apply: WatermarkConfigApply | Unset = UNSET
    enabled: bool | Unset = UNSET
    filter_id: None | str | Unset = UNSET
    seed_offset: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        apply: dict[str, Any] | Unset = UNSET
        if not isinstance(self.apply, Unset):
            apply = self.apply.to_dict()

        enabled = self.enabled

        filter_id: None | str | Unset
        if isinstance(self.filter_id, Unset):
            filter_id = UNSET
        else:
            filter_id = self.filter_id

        seed_offset = self.seed_offset

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if apply is not UNSET:
            field_dict["apply"] = apply
        if enabled is not UNSET:
            field_dict["enabled"] = enabled
        if filter_id is not UNSET:
            field_dict["filter_id"] = filter_id
        if seed_offset is not UNSET:
            field_dict["seed_offset"] = seed_offset

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.watermark_config_apply import WatermarkConfigApply

        d = dict(src_dict)
        _apply = d.pop("apply", UNSET)
        apply: WatermarkConfigApply | Unset
        if isinstance(_apply, Unset):
            apply = UNSET
        else:
            apply = WatermarkConfigApply.from_dict(_apply)

        enabled = d.pop("enabled", UNSET)

        def _parse_filter_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        filter_id = _parse_filter_id(d.pop("filter_id", UNSET))

        seed_offset = d.pop("seed_offset", UNSET)

        watermark_config = cls(
            apply=apply,
            enabled=enabled,
            filter_id=filter_id,
            seed_offset=seed_offset,
        )

        watermark_config.additional_properties = d
        return watermark_config

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
