import contextlib
import os
from pathlib import Path

from roly.config import RolyInputConfig, RunnerMode


@contextlib.contextmanager
def cd(path: Path) -> None:
    """Context manager to change the current working directory."""
    original_path = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_path)


def test_load_default_config() -> None:
    config = RolyInputConfig()
    print(config)


def test_load_config(tmp_path: Path) -> None:
    config_path = tmp_path / "roly.yaml"
    config_path.write_text("runner_mode: local")

    config_path = tmp_path / "roly_local.yaml"
    config_path.write_text("runner_mode: docker")

    with cd(tmp_path):
        config = RolyInputConfig(runner_mode=RunnerMode.Local)
        assert config.runner_mode.value == "local"
