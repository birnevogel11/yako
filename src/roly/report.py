from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from roly.test_module import TestSuiteResult


def report_test_suite_result(result: TestSuiteResult) -> None:
    raise NotImplementedError
