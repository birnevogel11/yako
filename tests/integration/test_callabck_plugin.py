import subprocess
from pathlib import Path

import pytest

from tests.integration.utils import run_ansible_playbook

TEST_PLAYBOOK_BASE_DIR = (Path(__file__).parent / "callback_plugin_playbooks").resolve()


def _run_test(filename: str, test_case_file_name: str) -> subprocess.CompletedProcess[str]:
    return run_ansible_playbook(TEST_PLAYBOOK_BASE_DIR / filename, TEST_PLAYBOOK_BASE_DIR / test_case_file_name)


@pytest.mark.integration
def test_roly_callback_basic(tmp_path: Path) -> None:
    result = _run_test("hello.yaml", "hello_test_case.yaml")

    assert not result.returncode
    assert "Hello World!" in result.stdout
