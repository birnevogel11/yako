import subprocess
from pathlib import Path

import pytest

from roly.single_runner import run_single_test

TEST_PLAYBOOK_BASE_DIR = (Path(__file__).parent / "test_callback_plugin").resolve()


def _run_test(test_case_file_name: str) -> subprocess.CompletedProcess[str]:
    return run_single_test(TEST_PLAYBOOK_BASE_DIR / test_case_file_name)


@pytest.mark.integration
def test_roly_callback_basic() -> None:
    result = _run_test("test_hello.yaml")

    assert not result.returncode
    assert "Hello World!" in result.stdout


@pytest.mark.integration
def test_roly_show_given_extra() -> None:
    result = _run_test("test_given_extra.yaml")

    assert not result.returncode
    assert "given_extra" in result.stdout
    assert "whats_life_mean_to_you" in result.stdout


@pytest.mark.integration
def test_roly_task_with_extra_vars() -> None:
    result = _run_test("test_task_extra_vars.yaml")

    assert not result.returncode
    assert "A book: whats_life_mean_to_you" in result.stdout
