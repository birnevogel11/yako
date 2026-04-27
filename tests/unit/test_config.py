import contextlib
import os
from pathlib import Path

from yako.config import RunnerMode, YakoInputConfig, init_config


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


def test_load_config_include(tmp_path: Path) -> None:
    config_path = tmp_path / "yako.yaml"
    config_path.write_text("given: !inc yako_given.yaml")

    config_path = tmp_path / "yako_given.yaml"
    config_path.write_text("vars:\n  test_var: this value")

    with cd(tmp_path):
        config = init_config()
        assert config.given.extra_vars["test_var"] == "this value"


def test_load_config_include_glob(tmp_path: Path) -> None:
    config_path = tmp_path / "yako.yaml"
    config_path.write_text("""
        given:
          vars:
            users: !inc user_*.yaml
    """)

    for i in range(3):
        config_path = tmp_path / f"user_{i}.yaml"
        config_path.write_text(f"""
            username: "user_{i}"
            index: {i}
        """)

    with cd(tmp_path):
        config = init_config()
        assert len(config.given.extra_vars["users"]) == 3
