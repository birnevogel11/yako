import contextlib
import os
from pathlib import Path

from yako.config import RunnerMode, YakoInputConfig


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
    config = YakoInputConfig()
    print(config)


def test_load_config(tmp_path: Path) -> None:
    config_path = tmp_path / "yako.yaml"
    config_path.write_text("runner_mode: local")

    config_path = tmp_path / "yako_local.yaml"
    config_path.write_text("runner_mode: docker")

    with cd(tmp_path):
        config = YakoInputConfig(runner_mode=RunnerMode.Local)
        assert config.runner_mode.value == "local"
