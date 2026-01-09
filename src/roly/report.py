from __future__ import annotations

from typing import TYPE_CHECKING

import rich.console

from roly.test_case import TestCaseResultState

if TYPE_CHECKING:
    from roly.test_module import TestSuiteResult


# TODO: implement it
def report_test_suite_result(result: TestSuiteResult) -> None:
    console = rich.console.Console()

    # Print summary

    # Print failed or errored test cases
    for case_result in result.test_case_results:
        if case_result.state in (TestCaseResultState.Error, TestCaseResultState.Failed):
            console.rule(f"Test Case: {case_result.name}", style="bold red")
            console.print(f"State: {case_result.state.value}", style="bold red")
            console.print("Stdout:", style="bold")
            console.print(case_result.stdout)
            console.print("Stderr:", style="bold")
            console.print(case_result.stderr)
            console.print("Return Code:", style="bold")
            console.print(case_result.return_code)

    # Print extra error messages
    for err_msg in result.extra_err_msgs:
        console.print(err_msg, style="bold orange")
