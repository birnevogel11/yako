from __future__ import annotations

import enum
import unittest
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from typing import Self


class FileMode(enum.Enum):
    No = "no"
    Left = "left"
    Right = "right"
    Both = "both"


class AssertMode(enum.Enum):
    Equal = "=="
    NotEqual = "!="
    Less = "<"
    Greater = ">"
    LessThen = "<="
    GreaterThan = ">="
    In = "in"
    NotIn = "not_in"
    IsNone = "is_none"
    IsNotNone = "is_not_none"
    IsTrue = "is_true"
    IsFalse = "is_false"
    IsNotTrue = "is_not_true"
    IsNotFalse = "is_not_false"


def _test_case_obj() -> unittest.TestCase:
    case = unittest.TestCase()
    case.maxDiff = 1024

    return case


MAPPING_ASSERT_FUNCTIONS = {
    AssertMode.Equal: lambda a, e: _test_case_obj().assertEqual(a, e),  # noqa: PT009
    AssertMode.NotEqual: lambda a, e: _test_case_obj().assertNotEqual(  # noqa: PT009
        a, e
    ),
    AssertMode.Less: lambda a, e: _test_case_obj().assertLess(a, e),  # noqa: PT009
    AssertMode.Greater: lambda a, e: _test_case_obj().assertGreater(  # noqa: PT009
        a, e
    ),
    AssertMode.LessThen: lambda a, e: _test_case_obj().assertLessEqual(  # noqa: PT009
        a, e
    ),
    AssertMode.GreaterThan: lambda a, e: _test_case_obj().assertGreaterEqual(  # noqa: PT009
        a, e
    ),
    AssertMode.In: lambda a, e: _test_case_obj().assertIn(a, e),  # noqa: PT009
    AssertMode.NotIn: lambda a, e: _test_case_obj().assertNotIn(a, e),  # noqa: PT009
    AssertMode.IsNone: lambda a, e: _test_case_obj().assertIsNone(  # noqa: ARG005, PT009
        a
    ),
    AssertMode.IsNotNone: lambda a, e: _test_case_obj().assertIsNotNone(  # noqa: ARG005, PT009
        a
    ),
    AssertMode.IsTrue: lambda a, e: _test_case_obj().assertTrue(  # noqa: ARG005, PT009
        a
    ),
    AssertMode.IsFalse: lambda a, e: _test_case_obj().assertFalse(  # noqa: ARG005, PT009
        a
    ),
    AssertMode.IsNotTrue: lambda a, e: _test_case_obj().assertFalse(  # noqa: ARG005, PT009
        a
    ),
    AssertMode.IsNotFalse: lambda a, e: _test_case_obj().assertTrue(  # noqa: ARG005, PT009
        a
    ),
}


class AssertResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    actual_value: Any | None
    expected_value: Any | None
    mode: AssertMode
    err_msg: str | None = None
    exception: Any | None = None


class AssertStmt(BaseModel):
    model_config = ConfigDict(frozen=True)

    actual: Any
    expected: Any | None = None
    mode: AssertMode = AssertMode.Equal
    msg: str | None = None
    file: FileMode = FileMode.No

    @model_validator(mode="after")  # type: ignore[misc]
    def validate_mode(self) -> Self:
        if (
            self.mode
            in (
                AssertMode.IsNone,
                AssertMode.IsNotNone,
                AssertMode.IsTrue,
                AssertMode.IsFalse,
                AssertMode.IsNotTrue,
                AssertMode.IsNotFalse,
            )
            and self.expected is not None
        ):
            msg = (
                "expected should not have value in these modes. "
                f"actual: {self.actual}, mode: {self.mode}"
            )
            raise ValueError(msg)

        return self

    def check(self) -> AssertResult:
        try:
            MAPPING_ASSERT_FUNCTIONS[self.mode](self.actual, self.expected)
        except AssertionError as err:
            return AssertResult(
                passed=False,
                actual_value=self.actual,
                expected_value=self.expected,
                mode=self.mode,
                err_msg=str(err) if not self.msg else f"{err} - {self.msg}",
            )

        return AssertResult(
            passed=True,
            actual_value=self.actual,
            expected_value=self.expected,
            mode=self.mode,
        )
