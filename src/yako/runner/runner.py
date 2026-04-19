from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from yako.config import RunnerMode, init_config
from yako.report import (
    report_list_only_test_cases,
    report_test_config,
    report_test_suite_result,
)
from yako.runner.docker_case_runner import DockerTestCaseRunner
from yako.runner.local_case_runner import LocalTestCaseRunner
from yako.runner.utils import Timer
from yako.test_case import TestCaseResult
from yako.test_module import TestSuite, TestSuiteResult, list_test_module_input_configs

if TYPE_CHECKING:
    import subprocess

    from yako.config import YakoConfig
    from yako.test_case import TestCase
    from yako.test_module import TestModule


logger = logging.getLogger(__name__)


class TestCaseRunner(Protocol):
    def init(self, base_dir: Path) -> None: ...
    def run(self, case: TestCase) -> subprocess.CompletedProcess[str]: ...


def _collect_test_cases(
    config: YakoConfig,
    filter_key: str = "",
    list_only: bool = False,
) -> tuple[list[tuple[TestModule, list[TestCase]]], list[str]]:
    # List test modules from input. Bypass any pydantic parse errors and
    # save in err_msgs
    raw_module_configs, err_msgs = list_test_module_input_configs(config)
    test_suite = TestSuite.from_raw_module_configs(config, raw_module_configs)

    collect_test_cases: list[tuple[TestModule, list[TestCase]]] = [
        (
            test_module,
            [
                case
                for case in sorted(test_module.test_cases, key=lambda c: c.display_name)
                if not list_only and (not filter_key or case.is_match(filter_key))
            ],
        )
        for test_module in sorted(test_suite.test_modules, key=lambda m: m.path)
    ]

    return collect_test_cases, err_msgs


def _run_test_cases(
    case_runner: TestCaseRunner,
    collect_test_cases: list[tuple[TestModule, list[TestCase]]],
    verbose_progress: bool,
) -> list[TestCaseResult]:
    """List all test cases from test modules and execute all matched test cases."""
    case_results: list[TestCaseResult] = []

    for test_module, test_cases in collect_test_cases:
        if not verbose_progress:
            print(str(test_module.path), end=" ", flush=True)

        for case in test_cases:
            if verbose_progress:
                print(case.display_name, end=" ", flush=True)

            if case.has_playbooks() and not case.does_playbook_exists():
                case_result = TestCaseResult.from_failed_without_playbooks_test_case(
                    case
                )
            else:
                cmd_result = case_runner.run(case)
                case_result = TestCaseResult.from_test_case_and_cmd_result(
                    case, cmd_result
                )

            case_results.append(case_result)

            if verbose_progress:
                print(f"... {case_result.state.to_result_str()}")
            else:
                print(case_result.state.to_short_result_str(), end="", flush=True)

        if not verbose_progress:
            print()

    return case_results


def run_test_suite(
    config: YakoConfig,
    case_runner: TestCaseRunner,
    filter_key: str = "",
    list_only: bool = False,
    verbose_progress: bool = False,
) -> TestSuiteResult:
    with tempfile.TemporaryDirectory() as raw_base_dir:
        case_runner.init(Path(raw_base_dir))
        collect_test_cases, err_msgs = _collect_test_cases(
            config, filter_key, list_only
        )
        case_results = _run_test_cases(
            case_runner, collect_test_cases, verbose_progress=verbose_progress
        )

        return TestSuiteResult.from_test_case_results(
            collect_test_cases, case_results, extra_err_msgs=err_msgs
        )


def run_tests(
    config: YakoConfig,
    filter_key: str = "",
    list_only: bool = False,
    verbose_progress: bool = False,
) -> TestSuiteResult:
    match config.runner_mode:
        case RunnerMode.Docker:
            case_runner: TestCaseRunner = DockerTestCaseRunner(config)
        case RunnerMode.Local:
            case_runner = LocalTestCaseRunner(config)

    return run_test_suite(
        config,
        case_runner,
        filter_key=filter_key,
        list_only=list_only,
        verbose_progress=verbose_progress,
    )


def run_tests_cli(
    base_path: list[Path] | None = None,
    config_path: Path | None = None,
    filter_key: str = "",
    list_only: bool = False,
    verbose: bool = False,
) -> None:
    with Timer() as timer:
        config = init_config(base_path, config_path)
        report_test_config(config)
        result = run_tests(
            config=config,
            filter_key=filter_key,
            list_only=list_only,
            verbose_progress=verbose,
        )
    result.execution_time_sec = timer.elapsed_time or 0.0

    report_test_suite_result(result)

    sys.exit(0 if result.is_success else 1)


def collect_tests_cli(
    base_path: list[Path] | None = None,
    config_path: Path | None = None,
    filter_key: str = "",
) -> None:
    with Timer() as timer:
        config = init_config(base_path, config_path)
        report_test_config(config)

        collected_test_cases, err_msgs = _collect_test_cases(
            config, filter_key=filter_key
        )

    report_list_only_test_cases(collected_test_cases, err_msgs, timer.elapsed_time or 0)
