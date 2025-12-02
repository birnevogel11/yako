from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from roly.config import RunnerMode, init_config
from roly.report import report_test_suite_result
from roly.runner.docker_case_runner import DockerTestCaseRunner
from roly.runner.local_case_runner import LocalTestCaseRunner
from roly.test_case import TestCaseResult
from roly.test_module import TestSuite, TestSuiteResult

if TYPE_CHECKING:
    import subprocess

    from roly.config import RolyConfig
    from roly.test_case import TestCase


logger = logging.getLogger(__name__)


class TestCaseRunner(Protocol):
    def init(self, base_dir: Path) -> None: ...
    def run(self, case: TestCase) -> subprocess.CompletedProcess[str]: ...


def run_test_suite(
    config: RolyConfig,
    case_runner: TestCaseRunner,
    filter_key: str = "",
    list_only: bool = False,
) -> TestSuiteResult:
    with tempfile.TemporaryDirectory() as raw_base_dir:
        base_dir = Path(raw_base_dir)

        case_runner.init(base_dir)

        # TODO: show parse error for test_*.yamls
        test_suite = TestSuite.from_config(config)
        # TODO: show playbook not found error for test cases
        test_cases = test_suite.list_test_cases()

        case_results: list[TestCaseResult] = []
        for case in test_cases:
            if not list_only and case.is_match(filter_key):
                cmd_result = case_runner.run(case)
                case_results.append(
                    TestCaseResult.from_test_case_and_cmd_result(case, cmd_result)
                )
            else:
                case_results.append(TestCaseResult.from_skipped_test_case(case))

        return TestSuiteResult.from_test_case_results(test_cases, case_results)


def run_tests(
    base_path: list[Path] | None = None,
    config_path: Path | None = None,
    filter_key: str = "",
    list_only: bool = False,
) -> TestSuiteResult:
    config = init_config(base_path, config_path)

    match config.runner_mode:
        case RunnerMode.Docker:
            case_runner: TestCaseRunner = DockerTestCaseRunner(config)
        case RunnerMode.Local:
            case_runner = LocalTestCaseRunner(config)

    return run_test_suite(
        config, case_runner, filter_key=filter_key, list_only=list_only
    )


def run_tests_cli(
    base_path: list[Path] | None = None,
    config_path: Path | None = None,
    filter_key: str = "",
    list_only: bool = False,
) -> None:
    result = run_tests(
        base_path=base_path,
        config_path=config_path,
        filter_key=filter_key,
        list_only=list_only,
    )
    report_test_suite_result(result)
