from __future__ import annotations

import itertools
import logging
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import pydantic
import yaml
from pydantic import BaseModel, ConfigDict

from yako.given import TestCaseGiven
from yako.test_case import (
    TestCase,
    TestCaseInputConfig,
    TestCaseResult,
    TestCaseResultState,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Self

    from yako.config import YakoConfig

logger = logging.getLogger(__name__)


class TestModuleInputConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    given: TestCaseGiven = TestCaseGiven()
    test_cases: list[TestCaseInputConfig] = []


class TestModule(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Path
    given: TestCaseGiven = TestCaseGiven()
    test_cases: list[TestCase] = []

    @classmethod
    def from_input_config(
        cls, config: YakoConfig, module_config: TestModuleInputConfig
    ) -> Self:
        test_cases = list(
            itertools.chain.from_iterable(
                TestCase.from_input_config(config, module_config, test_case)
                for test_case in module_config.test_cases
            )
        )
        return cls(
            path=module_config.path, given=module_config.given, test_cases=test_cases
        )


def _basic_check(base_dir: list[Path]) -> None:
    for base_path in base_dir:
        if not base_path.exists():
            msg = (
                "Input path does not exist. It must be a yaml file or a dir. "
                f"path: {base_path}"
            )
            raise ValueError(msg)


def _is_valid_test_filename(path: Path) -> bool:
    return path.is_file() and path.stem.startswith("test") and path.suffix == ".yaml"


def _list_test_modules(base_path: Path) -> Iterable[Path]:
    if _is_valid_test_filename(base_path):
        return (base_path,)
    if base_path.is_dir():
        test_modules_path = []
        for path in base_path.iterdir():
            if _is_valid_test_filename(path):
                test_modules_path.append(path)
            elif path.is_dir():
                test_modules_path.extend(_list_test_modules(path))
        return test_modules_path

    return ()


def list_test_module_input_configs(
    config: YakoConfig,
) -> tuple[list[TestModuleInputConfig], list[str]]:
    _basic_check(config.base_dir)

    test_modules_path = sorted(
        set(
            itertools.chain.from_iterable(
                _list_test_modules(base_path) for base_path in config.base_dir
            )
        )
    )

    module_configs = []
    err_msgs = []
    for path in test_modules_path:
        test_module_input_config = None
        try:
            test_module_input_config = TestModuleInputConfig.model_validate(
                {"path": path, **yaml.safe_load(path.read_text())}
            )
        except pydantic.ValidationError as err:
            msg = (
                "Failed to parse test module. Skip the file. "
                f"path: {path}, err: {err.errors()}"
            )
            err_msgs.append(msg)

        if test_module_input_config:
            module_configs.append(test_module_input_config)

    return module_configs, err_msgs


class TestSuite(BaseModel):
    test_modules: list[TestModule]

    @classmethod
    def from_raw_module_configs(
        cls, config: YakoConfig, raw_module_configs: list[TestModuleInputConfig]
    ) -> Self:
        return cls(
            test_modules=[
                TestModule.from_input_config(config, module_config)
                for module_config in raw_module_configs
            ]
        )

    def test_case_size(self) -> int:
        return sum(len(test_module.test_cases) for test_module in self.test_modules)

    def list_test_cases(self) -> list[TestCase]:
        test_cases = (
            test_case
            for test_module in self.test_modules
            for test_case in test_module.test_cases
        )

        return sorted(test_cases, key=lambda t: t.display_name)


class TestSuiteResult(BaseModel):
    is_success: bool = False
    total_test_cases: int = 0
    executed_test_cases: int = 0
    test_case_results: list[TestCaseResult] = []
    extra_err_msgs: list[str] = []
    execution_time_sec: float = 0.0

    @classmethod
    def from_test_case_results(
        cls,
        module_cases: list[tuple[TestModule, list[TestCase]]],
        case_results: list[TestCaseResult],
        extra_err_msgs: list[str] | None = None,
    ) -> Self:
        return cls(
            is_success=all(
                result.state
                in (TestCaseResultState.Success, TestCaseResultState.Skipped)
                for result in case_results
            ),
            total_test_cases=sum(len(cases) for _, cases in module_cases),
            executed_test_cases=len(
                [result.state != TestCaseResultState.Skipped for result in case_results]
            ),
            test_case_results=case_results,
            extra_err_msgs=extra_err_msgs or [],
            execution_time_sec=sum(
                result.execution_time_secs for result in case_results
            ),
        )
