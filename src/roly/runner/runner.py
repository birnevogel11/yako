from __future__ import annotations

import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from roly.config import RunnerMode, init_config
from roly.report import report_test_suite_result
from roly.runner.docker_case_runner import DockerTestCaseRunner
from roly.runner.local_case_runner import LocalTestCaseRunner
from roly.test_case import TestCaseResult
from roly.test_module import TestSuite, TestSuiteResult, list_test_module_input_configs2

if TYPE_CHECKING:
    import subprocess
    from typing import Self

    from roly.config import RolyConfig
    from roly.test_case import TestCase
    from roly.test_module import TestModule


logger = logging.getLogger(__name__)


class Timer:
    def __init__(self) -> None:
        self.start_time: float | None = None
        self.elapsed_time: float | None = None

    def __enter__(self) -> Self:
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.start_time is not None:
            self.elapsed_time = time.time() - self.start_time


class TestCaseRunner(Protocol):
    def init(self, base_dir: Path) -> None: ...
    def run(self, case: TestCase) -> subprocess.CompletedProcess[str]: ...


def run_test_suite(
    config: RolyConfig,
    case_runner: TestCaseRunner,
    filter_key: str = "",
    list_only: bool = False,
    verbose_progress: bool = False,
) -> TestSuiteResult:
    with tempfile.TemporaryDirectory() as raw_base_dir:
        base_dir = Path(raw_base_dir)

        case_runner.init(base_dir)

        # List test modules from input. Bypass any pydantic parse errors and
        # save in err_msgs
        raw_module_configs, err_msgs = list_test_module_input_configs2(config)
        test_suite = TestSuite.from_raw_module_configs(config, raw_module_configs)

        # List all test cases from test modules and execute all matched test cases
        case_results: list[TestCaseResult] = []

        collect_test_cases: list[tuple[TestModule, list[TestCase]]] = [
            (
                test_module,
                [
                    case
                    for case in sorted(
                        test_module.test_cases, key=lambda c: c.display_name
                    )
                    if not list_only and (not filter_key or case.is_match(filter_key))
                ],
            )
            for test_module in sorted(test_suite.test_modules, key=lambda m: m.path)
        ]

        for test_module, test_cases in collect_test_cases:
            if not verbose_progress:
                print(str(test_module.path), end=" ", flush=True)

            for case in test_cases:
                if verbose_progress:
                    print(case.display_name, end=" ", flush=True)

                case_result = None
                if case.has_playbooks() and not case.does_playbook_exists():
                    case_result = (
                        TestCaseResult.from_failed_without_playbooks_test_case(case)
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

        return TestSuiteResult.from_test_case_results(
            collect_test_cases, case_results, extra_err_msgs=err_msgs
        )


def run_tests(
    base_path: list[Path] | None = None,
    config_path: Path | None = None,
    filter_key: str = "",
    list_only: bool = False,
    verbose_progress: bool = False,
) -> TestSuiteResult:
    config = init_config(base_path, config_path)

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
        result = run_tests(
            base_path=base_path,
            config_path=config_path,
            filter_key=filter_key,
            list_only=list_only,
            verbose_progress=verbose,
        )

    result.execution_time_sec = timer.elapsed_time or 0.0

    report_test_suite_result(result)

    sys.exit(0 if result.is_success else 1)
