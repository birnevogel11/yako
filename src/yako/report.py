from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import rich.console

from yako.test_case import TestCaseResultState

if TYPE_CHECKING:
    from yako.config import YakoConfig
    from yako.test_case import TestCase
    from yako.test_module import TestModule, TestSuiteResult

console = rich.console.Console()


def print_failure_cases(result: TestSuiteResult) -> None:
    failed_results = (
        case_result
        for case_result in result.test_case_results
        if case_result.state
        in (
            TestCaseResultState.Error,
            TestCaseResultState.Failed,
        )
    )
    for case_result in failed_results:
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
        print(case_result.stdout)
        console.print("Stderr:", style="bold")
        print(case_result.stderr)


def print_error_messages(extra_err_msgs: list[str]) -> None:
    for err_msg in extra_err_msgs:
        console.print(err_msg, style="bold")


def _print_summary_line(summary_tokens: list[str], execution_time_sec: float) -> None:
    tokens = [*summary_tokens, f"in {execution_time_sec:.2f}sec"]

    console.print()
    console.rule(" ".join(tokens), align="center", characters="=")


def _collect_summary_tokens(result: TestSuiteResult) -> tuple[list[str], float]:
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

    return summary_tokens, result.execution_time_sec or 0


def print_summary(result: TestSuiteResult) -> None:
    summary_tokens, execution_time_secs = _collect_summary_tokens(result)
    _print_summary_line(summary_tokens, execution_time_secs)


def report_test_config(config: YakoConfig) -> None:
    console.rule("[bold]Yako test session starts[/]", align="center", characters="=")
    console.print(
        "base path(s):", ", ".join(str(p) for p in config.base_dir), highlight=False
    )
    console.print("runner mode:", config.runner_mode.value)
    console.print()


def report_test_suite_result(result: TestSuiteResult) -> None:
    print_failure_cases(result)
    print_error_messages(result.extra_err_msgs)
    print_summary(result)


def report_list_only_test_cases(
    collected_test_cases: list[tuple[TestModule, list[TestCase]]],
    err_msgs: list[str],
    execution_time_sec: float,
) -> None:
    total_test_cases = sum((len(test_cases) for _, test_cases in collected_test_cases))

    for test_module, test_cases in collected_test_cases:
        console.print(f"<Path {test_module.path}>", highlight=False)
        for test_case in test_cases:
            console.print(
                f"    <TestCase {test_case.list_only_name()}>", highlight=False
            )

    if err_msgs:
        console.print("Collect errors:")
        print_error_messages(err_msgs)

    _print_summary_line([f"Collect {total_test_cases} test cases"], execution_time_sec)
