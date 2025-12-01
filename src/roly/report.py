from __future__ import annotations

from typing import TYPE_CHECKING

import rich

if TYPE_CHECKING:
    from roly.test_module import TestSuiteResult


def report_test_suite_result(result: TestSuiteResult) -> None:
    rich.print(result)
    print(result.test_case_results[0].stdout)
