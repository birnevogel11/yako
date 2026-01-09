from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import rich.console

from roly.test_case import TestCaseResultState

if TYPE_CHECKING:
    from roly.config import RolyConfig
    from roly.test_module import TestSuiteResult

console = rich.console.Console()


def print_failure_cases(result: TestSuiteResult) -> None:
    for case_result in result.test_case_results:
        if case_result.state in (
            TestCaseResultState.Error,
            TestCaseResultState.Failed,
        ):
            console.rule(
                (
                    f"Test Case: {case_result.name}, "
                    f"State: {case_result.state.to_result_str()}"
                ),
                style="bold red",
                align="center",
            )
            console.print("Return Code:", style="bold")
            console.print(case_result.return_code)
            console.print("Stdout:", style="bold")
            console.print(case_result.stdout)
            console.print("Stderr:", style="bold")
            console.print(case_result.stderr)


def print_extra_error_messages(result: TestSuiteResult) -> None:
    for err_msg in result.extra_err_msgs:
        console.print(err_msg, style="bold orange")


def print_summary_line(result: TestSuiteResult) -> None:
    total_counts: defaultdict[TestCaseResultState, int] = defaultdict(int)
    for case_result in result.test_case_results:
        total_counts[case_result.state] += 1

    summary_tokens = []
    if total_counts[TestCaseResultState.Success]:
        summary_tokens.append(
            f"[bold green]{total_counts[TestCaseResultState.Success]} passed[/]"
        )
    if total_counts[TestCaseResultState.Failed]:
        summary_tokens.append(
            f"[bold red]{total_counts[TestCaseResultState.Failed]} failed[/]"
        )
    if total_counts[TestCaseResultState.Error]:
        summary_tokens.append(
            f"[bold red]{total_counts[TestCaseResultState.Error]} errors[/]"
        )
    if total_counts[TestCaseResultState.Skipped]:
        summary_tokens.append(
            f"[bold yellow]{total_counts[TestCaseResultState.Skipped]} skipped[/]"
        )
    if result.execution_time_sec:
        summary_tokens.append(f"in {result.execution_time_sec:.2f} sec")

    console.print()
    console.rule(" ".join(summary_tokens), align="center", characters="=")


def report_test_config(config: RolyConfig) -> None:
    console.print(
        "base path(s):", ", ".join(str(p) for p in config.base_dir), style=None
    )
    console.print("runner mode:", config.runner_mode.value)
    console.print()


def report_test_suite_result(result: TestSuiteResult) -> None:
    print_failure_cases(result)
    print_extra_error_messages(result)
    print_summary_line(result)
