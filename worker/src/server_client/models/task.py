from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.task_args_control import TaskArgsControl
    from ..models.task_args_keyword import TaskArgsKeyword
    from ..models.task_args_positional import TaskArgsPositional


T = TypeVar("T", bound="Task")


@_attrs_define
class Task:
    """タスク

    Attributes:
        args_control (TaskArgsControl): 制御情報
        args_keyword (TaskArgsKeyword): キーワード引数
        args_positional (TaskArgsPositional): 位置引数
        id (UUID): id
        task (str): タスク名
        error_message (None | str | Unset): エラーメッセージ
    """

    args_control: TaskArgsControl
    args_keyword: TaskArgsKeyword
    args_positional: TaskArgsPositional
    id: UUID
    task: str
    error_message: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        args_control = self.args_control.to_dict()

        args_keyword = self.args_keyword.to_dict()

        args_positional = self.args_positional.to_dict()

        id = str(self.id)

        task = self.task

        error_message: None | str | Unset
        if isinstance(self.error_message, Unset):
            error_message = UNSET
        else:
            error_message = self.error_message

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "args_control": args_control,
                "args_keyword": args_keyword,
                "args_positional": args_positional,
                "id": id,
                "task": task,
            }
        )
        if error_message is not UNSET:
            field_dict["error_message"] = error_message

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.task_args_control import TaskArgsControl
        from ..models.task_args_keyword import TaskArgsKeyword
        from ..models.task_args_positional import TaskArgsPositional

        d = dict(src_dict)
        args_control = TaskArgsControl.from_dict(d.pop("args_control"))

        args_keyword = TaskArgsKeyword.from_dict(d.pop("args_keyword"))

        args_positional = TaskArgsPositional.from_dict(d.pop("args_positional"))

        id = UUID(d.pop("id"))

        task = d.pop("task")

        def _parse_error_message(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error_message = _parse_error_message(d.pop("error_message", UNSET))

        task = cls(
            args_control=args_control,
            args_keyword=args_keyword,
            args_positional=args_positional,
            id=id,
            task=task,
            error_message=error_message,
        )

        task.additional_properties = d
        return task

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
