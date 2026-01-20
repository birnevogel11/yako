from __future__ import annotations

import itertools
from collections import ChainMap
from typing import TYPE_CHECKING, Annotated, Any

import ansible
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    ValidationError,
)

from roly.assert_check import AssertMode, AssertResult, AssertStmt, FileMode

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, Self


class MockActionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    result_dicts: dict[str, Any] = {}
    changed: bool = False

    def gen_action(
        self, original_action_name: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        new_action_name = "roly_mock"
        new_action_name_args = {
            "task_name": new_action_name,
            "original_module_name": original_action_name,
            "consider_changed": self.changed,
            "result_dict": self.result_dicts,
        }
        return new_action_name, new_action_name_args


def _ensure_custom_action(
    value: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if len(value) != 1:
        raise ValueError("custom_action must have exactly one key-value pair")
    return value


class MockActionCustomConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    custom_action: Annotated[
        dict[str, dict[str, Any]], AfterValidator(_ensure_custom_action)
    ]

    def gen_action(
        self, original_action_name: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        new_action_name = next(iter(self.custom_action.keys()))
        return new_action_name, self.custom_action[new_action_name]


class TestCaseAssert(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = ""
    value: Any | None = None
    mode: AssertMode = AssertMode.Equal
    msg: str | None = None
    file: FileMode = FileMode.No

    # TODO: (bv11) Check valid state, mode=after

    def check(self, get_actual_value_func: Callable[[str], Any]) -> AssertResult:
        result = None
        try:
            result = self._to_assert_stmt(get_actual_value_func).check()
        except (KeyError, ansible.errors.AnsibleUndefinedVariable) as err:
            result = self._to_var_not_found_result(err)
        except Exception as err:  # noqa: BLE001
            result = self._to_unknown_error_result(err)

        return result

    def _to_assert_stmt(
        self, get_actual_value_func: Callable[[str], Any]
    ) -> AssertStmt:
        return AssertStmt(
            actual=get_actual_value_func(self.name),
            expected=self.value,
            mode=self.mode,
            file=self.file,
            msg=self.msg or f"variable name: {self.name}",
        )

    def _to_unknown_error_result(
        self, err: Exception, msg: str | None = None
    ) -> AssertResult:
        msg = (
            msg
            or f"Unknown error. assert_stmt: {self}, err: {err}, err_type: {type(err)}"
        )
        return AssertResult(
            passed=False,
            actual_value=None,
            expected_value=self.value,
            mode=self.mode,
            err_msg=msg,
        )

    def _to_var_not_found_result(self, err: Exception) -> AssertResult:
        return self._to_unknown_error_result(
            err, f"Variable: {self.name} not found, err: {err}"
        )


class TestTaskConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    extra_vars: dict[str, Any] = {}
    mock: MockActionConfig | MockActionCustomConfig | None = None

    assert_inputs: list[TestCaseAssert] = []
    assert_outputs: list[TestCaseAssert] = []

    should_be_skipped: bool | None = None
    should_be_changed: bool | None = None
    should_fail: bool | None = None


class CopyFileConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    src: str
    dest: str

    @classmethod
    def from_src(cls, src: str) -> Self:
        return cls(src=src, dest=src if not src.endswith("/") else src.rstrip("/"))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        if "src" in data and "dest" in data:
            return cls(src=data["src"], dest=data["dest"])
        raise ValidationError("CopyFileConfig dict must have 'src' and 'dest' keys")


def _parse_copy_file_config_list(value: Any) -> list[CopyFileConfig]:
    if not isinstance(value, list):
        raise ValidationError("files must be a list")

    parsed_values = []
    for item in value:
        match item:
            case CopyFileConfig():
                parsed_values.append(item)
            case str():
                parsed_values.append(CopyFileConfig.from_src(item))
            case dict():
                parsed_values.append(CopyFileConfig.from_dict(item))
            case _:
                raise ValidationError(
                    "Each item in files list must be either a string or a dict"
                )
    return parsed_values


class TestCaseGiven(BaseModel):
    model_config = ConfigDict(frozen=True)

    files: Annotated[
        list[CopyFileConfig], BeforeValidator(_parse_copy_file_config_list)
    ] = []
    extra_vars: dict[str, Any] = {}
    mock_tasks: list[TestTaskConfig] = []

    @classmethod
    def from_merge(cls, *givens: Self) -> Self:
        return cls.model_validate(
            {
                "files": list(
                    itertools.chain.from_iterable(given.files for given in givens)
                ),
                "extra_vars": dict(ChainMap(*(given.extra_vars for given in givens))),
                "mock_tasks": list(
                    itertools.chain.from_iterable(given.mock_tasks for given in givens),
                ),
            }
        )
