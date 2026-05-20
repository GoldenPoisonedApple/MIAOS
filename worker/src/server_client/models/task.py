from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

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
        experiment_id (int): 実験ID
        id (UUID): id
        task (str): タスク名
    """

    args_control: TaskArgsControl
    args_keyword: TaskArgsKeyword
    args_positional: TaskArgsPositional
    experiment_id: int
    id: UUID
    task: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        args_control = self.args_control.to_dict()

        args_keyword = self.args_keyword.to_dict()

        args_positional = self.args_positional.to_dict()

        experiment_id = self.experiment_id

        id = str(self.id)

        task = self.task

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "args_control": args_control,
                "args_keyword": args_keyword,
                "args_positional": args_positional,
                "experiment_id": experiment_id,
                "id": id,
                "task": task,
            }
        )

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

        experiment_id = d.pop("experiment_id")

        id = UUID(d.pop("id"))

        task = d.pop("task")

        task = cls(
            args_control=args_control,
            args_keyword=args_keyword,
            args_positional=args_positional,
            experiment_id=experiment_id,
            id=id,
            task=task,
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
