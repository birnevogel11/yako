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


MAPPING_ASSERT_FUNCTIONS = {
    AssertMode.Equal: lambda a, e: unittest.TestCase().assertEqual(a, e),  # noqa: PT009
    AssertMode.NotEqual: lambda a, e: unittest.TestCase().assertNotEqual(a, e),
    AssertMode.Less: lambda a, e: unittest.TestCase().assertLess(a, e),  # noqa: PT009
    AssertMode.Greater: lambda a, e: unittest.TestCase().assertGreater(a, e),
    AssertMode.LessThen: lambda a, e: unittest.TestCase().assertLessEqual(a, e),
    AssertMode.GreaterThan: lambda a, e: unittest.TestCase().assertGreaterEqual(a, e),
    AssertMode.In: lambda a, e: unittest.TestCase().assertIn(a, e),  # noqa: PT009
    AssertMode.NotIn: lambda a, e: unittest.TestCase().assertNotIn(a, e),  # noqa: PT009
    AssertMode.IsNone: lambda a, e: unittest.TestCase().assertIsNone(a),
    AssertMode.IsNotNone: lambda a, e: unittest.TestCase().assertIsNotNone(a),
    AssertMode.IsTrue: lambda a, e: unittest.TestCase().assertTrue(a),
    AssertMode.IsFalse: lambda a, e: unittest.TestCase().assertFalse(a),
    AssertMode.IsNotTrue: lambda a, e: unittest.TestCase().assertFalse(a),
    AssertMode.IsNotFalse: lambda a, e: unittest.TestCase().assertTrue(a),
}


class AssertResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    actual_value: Any | None
    expected_value: Any | None
    mode: AssertMode
    err_msg: str | None = None


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
