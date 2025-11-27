from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from roly.config import RunnerMode, init_config
from roly.runner.docker_runner import run_tests_docker
from roly.runner.local_runner import run_tests_local
from roly.test_module import list_test_modules

if TYPE_CHECKING:
    from pathlib import Path


logger = logging.getLogger(__name__)


def run_tests(
    base_path: list[Path] | None = None, config_path: Path | None = None
) -> None:
    config = init_config(base_path, config_path)
    test_modules = list_test_modules(config)

    match config.runner_mode:
        case RunnerMode.Docker:
            run_tests_docker(config, test_modules)
        case RunnerMode.Local:
            run_tests_local(config, test_modules)


def run_test_cli(
    base_path: list[Path] | None = None, config_path: Path | None = None
) -> None:
    run_tests(base_path=base_path, config_path=config_path)
