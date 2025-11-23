from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from roly.config import RolyConfig
    from roly.test_module import TestModule

logger = logging.getLogger(__name__)


def run_tests_docker(config: RolyConfig, test_modules: list[TestModule]) -> None:
    raise NotImplementedError
