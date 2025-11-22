from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from roly.config import init_config

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def run_test_cli(
    base_path: list[Path] | None = None, config_path: list[Path] | None = None
) -> None:
    config = init_config(config_path, base_path)
    print(config)
