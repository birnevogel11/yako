from typing import Any

import pydantic
import pytest
from inline_snapshot import snapshot

from yako.assert_check import AssertMode, AssertStmt


def test_validate_input_mode() -> None:
    input_json = {
        "actual": {"a": 1},
        "expected": {"b": 2},
    }
    stmt = AssertStmt.model_validate(input_json)
    assert stmt == snapshot(AssertStmt(actual={"a": 1}, expected={"b": 2}))


def test_validate_input_mode_failed() -> None:
    with pytest.raises(pydantic.ValidationError):
        AssertStmt(actual={"a": 1}, expected={"b": 2}, mode=AssertMode.IsFalse)


def test_validate_input_mode_failed_with_json() -> None:
    input_json = {
        "actual": {"a": 1},
        "expected": {"b": 2},
        "mode": "is_true",
    }
    with pytest.raises(pydantic.ValidationError):
        AssertStmt.model_validate(input_json)


def test_assert_check_true() -> None:
    result = AssertStmt(actual={"a": 1}, expected={"b": 2}).check()
    assert not result.passed
    assert result.err_msg == snapshot(
        """\
{'a': 1} != {'b': 2}
- {'a': 1}
?   ^   ^

+ {'b': 2}
?   ^   ^
""",
    )


@pytest.mark.parametrize(
    ("actual", "expected", "mode"),
    [
        (2, 2, "=="),
        (2, 3, "!="),
        (2, 3, "<"),
        (2, 3, "<="),
        (3, 2, ">"),
        (3, 2, ">="),
        (2, [2], "in"),
        (2, [], "not_in"),
        (2, None, "is_true"),
        (None, None, "is_none"),
        ([2], None, "is_not_none"),
        ([], None, "is_false"),
        ([], None, "is_not_true"),
        (2, None, "is_not_false"),
    ],
)
def test_assert_check(actual: Any, expected: Any, mode: str) -> None:
    assert (
        AssertStmt.model_validate(
            {"actual": actual, "expected": expected, "mode": mode}
        )
        .check()
        .passed
    )


@pytest.mark.parametrize(
    ("actual", "expected", "mode", "msg"),
    [
        (2, 3, "==", snapshot("2 != 3")),
        (2, 2, "!=", snapshot("2 == 2")),
        (3, 2, "<", snapshot("3 not less than 2")),
        (3, 2, "<=", snapshot("3 not less than or equal to 2")),
        (2, 3, ">", snapshot("2 not greater than 3")),
        (2, 3, ">=", snapshot("2 not greater than or equal to 3")),
        (2, [], "in", snapshot("2 not found in []")),
        (2, [2], "not_in", snapshot("2 unexpectedly found in [2]")),
        (2, None, "is_none", snapshot("2 is not None")),
        (None, None, "is_not_none", snapshot("unexpectedly None")),
        (0, None, "is_true", snapshot("0 is not true")),
        (2, None, "is_false", snapshot("2 is not false")),
        ([2], None, "is_not_true", snapshot("[2] is not false")),
        ([], None, "is_not_false", snapshot("[] is not true")),
    ],
)
def test_assert_check_failed(actual: Any, expected: Any, mode: str, msg: str) -> None:
    result = AssertStmt.model_validate(
        {"actual": actual, "expected": expected, "mode": mode}
    ).check()
    assert not result.passed
    assert result.err_msg == msg
