from __future__ import annotations

import logging
from pathlib import Path

from roly.config import init_config

logger = logging.getLogger(__name__)


def run_test_cli(
    base_path: list[Path] | None = None, config_path: list[Path] | None = None
) -> None:
    config = init_config(config_path, base_path)
