from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict

from roly.assert_check import AssertMode, AssertResult, AssertStmt, FileMode

if TYPE_CHECKING:
    from collections.abc import Callable


class MockActionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    result_dicts: dict[str, Any] = {}
    files: dict[str, str] = {}
    changed: bool = False

    def gen_action(self, original_action_name: str | None = None) -> tuple[str, dict[str, Any]]:
        new_action_name = "roly_mock"
        new_action_name_args = {
            "task_name": new_action_name,
            "original_module_name": original_action_name,
            "consider_changed": self.changed,
            "result_dict": self.result_dicts,
        }
        return new_action_name, new_action_name_args


def _ensure_custom_action(value: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if len(value) != 1:
        raise ValueError("custom_action must have exactly one key-value pair")
    return value


class MockActionCustomConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    custom_action: Annotated[dict[str, dict[str, Any]], AfterValidator(_ensure_custom_action)]

    def gen_action(self, original_action_name: str | None = None) -> tuple[str, dict[str, Any]]:
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
        except KeyError as err:
            result = self._to_var_not_found_result(err)
        except Exception as err:  # noqa: BLE001
            result = self._to_unknown_error_result(err)

        return result

    def _to_assert_stmt(self, get_actual_value_func: Callable[[str], Any]) -> AssertStmt:
        return AssertStmt(
            actual=get_actual_value_func(self.name),
            expected=self.value,
            mode=self.mode,
            file=self.file,
            msg=self.msg,
        )

    def _to_unknown_error_result(self, err: Exception, msg: str | None = None) -> AssertResult:
        msg = msg or f"Unknown error. assert_stmt: {self}, err: {err}"
        return AssertResult(
            passed=False,
            actual_value=None,
            expected_value=self.value,
            mode=self.mode,
            err_msg=msg,
        )

    def _to_var_not_found_result(self, err: Exception) -> AssertResult:
        return self._to_unknown_error_result(err, f"Input variable: {self.name} not found, err: {err}")


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


class TestCaseGiven(BaseModel):
    model_config = ConfigDict(frozen=True)

    files: dict[str, str] = {}
    extra_vars: dict[str, Any] = {}
    mock_tasks: list[TestTaskConfig] = []
