from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pydantic
import pytest
from inline_snapshot import snapshot

from yako.assert_check import AssertMode, AssertResult, FileMode
from yako.given import (
    CopyFileConfig,
    MockActionCustomConfig,
    TestCaseAssert,
    TestCaseGiven,
)

if TYPE_CHECKING:
    from typing import Any


@pytest.mark.parametrize(
    ("raw_file_field", "expected_file_field"),
    [
        (
            ["/path/to/src.txt"],
            snapshot([CopyFileConfig(src="/path/to/src.txt", dest="/path/to/src.txt")]),
        ),
        (
            [{"src": "/path/to/src.txt", "dest": "/path/to/dest.txt"}],
            snapshot(
                [CopyFileConfig(src="/path/to/src.txt", dest="/path/to/dest.txt")]
            ),
        ),
    ],
)
def test_parse_files_field(
    raw_file_field: list[Any], expected_file_field: list[CopyFileConfig]
) -> None:
    given = TestCaseGiven.model_validate({"files": raw_file_field})
    assert given.files == expected_file_field


def test_custom_action_config() -> None:
    raw_custom_action = {
        "custom_action": {
            "set_fact": {"answer": 42},
        }
    }

    custom_config = MockActionCustomConfig.model_validate(raw_custom_action)
    assert custom_config == snapshot(
        MockActionCustomConfig(custom_action={"set_fact": {"answer": 42}})
    )


def test_invalid_custom_action_config() -> None:
    raw_custom_action = {
        "custom_action": {
            "set_fact": {"answer": 42},
            "another_fact": {"answer": 43},
        }
    }

    with pytest.raises(pydantic.ValidationError) as err:
        MockActionCustomConfig.model_validate(raw_custom_action)

    assert json.loads(err.value.json()) == snapshot(
        [
            {
                "type": "value_error",
                "loc": ["custom_action"],
                "msg": "Value error, custom_action must have "
                "exactly one key-value pair",
                "input": {
                    "set_fact": {"answer": 42},
                    "another_fact": {"answer": 43},
                },
                "ctx": {"error": "custom_action must have exactly one key-value pair"},
                "url": "https://errors.pydantic.dev/2.12/v/value_error",
            }
        ]
    )


@pytest.mark.parametrize(
    ("assert_value", "expected_result"),
    [
        (
            42,
            snapshot(
                AssertResult(
                    passed=True,
                    actual_value=42,
                    expected_value=42,
                    mode=AssertMode.Equal,
                )
            ),
        ),
        (
            43,
            snapshot(
                AssertResult(
                    passed=False,
                    actual_value=43,
                    expected_value=42,
                    mode=AssertMode.Equal,
                    err_msg="43 != 42 - variable name: fake_var",
                )
            ),
        ),
    ],
)
def test_test_case_assert(assert_value: int, expected_result: AssertResult) -> None:
    config = TestCaseAssert(name="fake_var", value=42)
    assert config.check(lambda _: assert_value) == expected_result


def test_test_case_assert_var_name_not_found() -> None:
    def not_found(var_name: str) -> None:
        msg = f"{var_name} not found"
        raise KeyError(msg)

    config = TestCaseAssert(name="fake_var", value=42)

    assert config.check(not_found) == snapshot(
        AssertResult(
            passed=False,
            actual_value=None,
            expected_value=42,
            mode=AssertMode.Equal,
            err_msg="Variable: fake_var not found, err: 'fake_var not found'",
        )
    )


def test_test_case_assert_unpected_exception() -> None:
    def unknown_exception(var_name: str) -> None:  # noqa: ARG001
        raise Exception("unknown exception")  # noqa: TRY002

    config = TestCaseAssert(name="fake_var", value=42)

    assert config.check(unknown_exception) == snapshot(
        AssertResult(
            passed=False,
            actual_value=None,
            expected_value=42,
            mode=AssertMode.Equal,
            err_msg="Unknown error. "
            "assert_stmt: name='fake_var' value=42 mode=<AssertMode.Equal: '=='> "
            "msg=None file=<FileMode.No: 'no'>, "
            "err: unknown exception, err_type: <class 'Exception'>",
        )
    )


@pytest.mark.parametrize(
    "assert_mode",
    [AssertMode.IsTrue, AssertMode.IsFalse, AssertMode.IsNone, AssertMode.IsNotNone],
)
def test_test_case_assert_basic_input_check(assert_mode: AssertMode) -> None:
    with pytest.raises(pydantic.ValidationError):
        TestCaseAssert(name="fake_var", value=42, mode=assert_mode)


@pytest.mark.parametrize("file_mode", [FileMode.Left, FileMode.Both])
def test_test_case_assert_basic_file_mode_check(file_mode: FileMode) -> None:
    with pytest.raises(pydantic.ValidationError):
        TestCaseAssert(name="fake_var", value="/path/to/file", file=file_mode)
