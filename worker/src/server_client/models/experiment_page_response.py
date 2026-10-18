from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.model import Model


T = TypeVar("T", bound="ExperimentPageResponse")


@_attrs_define
class ExperimentPageResponse:
    """実験一覧のページングレスポンス

    Attributes:
        items (list[Model]): 当該ページの実験
        limit (int): 返却した limit（実質 100）
        page (int): 返却したページ番号（1始まり）
        total (int): 全件数
    """

    items: list[Model]
    limit: int
    page: int
    total: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        limit = self.limit

        page = self.page

        total = self.total

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "items": items,
                "limit": limit,
                "page": page,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.model import Model

        d = dict(src_dict)
        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = Model.from_dict(items_item_data)

            items.append(items_item)

        limit = d.pop("limit")

        page = d.pop("page")

        total = d.pop("total")

        experiment_page_response = cls(
            items=items,
            limit=limit,
            page=page,
            total=total,
        )

        experiment_page_response.additional_properties = d
        return experiment_page_response

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
