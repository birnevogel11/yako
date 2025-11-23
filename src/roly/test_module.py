from __future__ import annotations

import itertools
import logging
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING

import pydantic
import yaml
from pydantic import BaseModel, ConfigDict

from roly.test_case import TestCase, TestCaseGiven, TestCaseInputConfig

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Self

    from roly.config import RolyConfig

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
        cls, config: RolyConfig, module_config: TestModuleInputConfig
    ) -> Self:
        test_cases = list(
            itertools.chain.from_iterable(
                TestCase.from_config(config, module_config, test_case)
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


def _list_test_module_input_configs(config: RolyConfig) -> list[TestModuleInputConfig]:
    _basic_check(config.base_dir)

    test_modules_path = sorted(
        set(
            itertools.chain.from_iterable(
                _list_test_modules(base_path) for base_path in config.base_dir
            )
        )
    )

    module_configs = []
    for path in test_modules_path:
        try:
            test_module_input_config = TestModuleInputConfig.model_validate(
                {*{"path": path}, *yaml.safe_load(path.read_text())}
            )
        except pydantic.ValidationError:
            logger.warning("Failed to parse test module. Skip the file. path: %s", path)

        module_configs.append(test_module_input_config)

    return module_configs


def list_test_modules(config: RolyConfig) -> list[TestModule]:
    return [
        TestModule.from_input_config(config, module_config)
        for module_config in _list_test_module_input_configs(config)
    ]
