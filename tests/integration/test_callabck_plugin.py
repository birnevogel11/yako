from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from roly.ansible import make_roly_ansible_config
from roly.consts import ROLY_TEST_CONFIG_KEY
from roly.test_case import TestCaseInputConfig

TEST_PLAYBOOK_BASE_DIR = (Path(__file__).parent / "test_callback_plugin").resolve()

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)

PLAYBOOK_DEFAULT_CONTENT = {
    "hosts": "all",
    "any_errors_fatal": True,
    "gather_facts": False,
}


def _make_content_playbook(raw_content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**PLAYBOOK_DEFAULT_CONTENT, "tasks": raw_content}]


def _search_ansible_playbook() -> Path | None:
    bin_path = Path(sys.executable).parent / "ansible-playbook"
    if bin_path.exists():
        return bin_path

    if default_bin_path := shutil.which("ansible-playbook"):
        return Path(default_bin_path)

    return None


def _run_ansible_playbook(
    *,
    ws_dir: Path,
    playbook_path: Path,
    roly_test_case_path: Path,
    ansible_cfg_path: Path,
    extra_args: list[str] | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    ansible_playbook_bin = _search_ansible_playbook()
    if not ansible_playbook_bin:
        raise RuntimeError("ansible-playbook is unavailable.")

    env = {
        "ANSIBLE_CONFIG": str(ansible_cfg_path),
        "ANSIBLE_STDOUT_CALLBACK": "debug",
    }
    cmd: tuple[str, ...] = (
        *(
            str(ansible_playbook_bin),
            "-v",
            "--connection=local",
            "--inventory",
            "127.0.0.1,",
            "--limit",
            "127.0.0.1",
            "-e",
            f"@{roly_test_case_path.resolve()}",
        ),
        *(extra_args or ()),
        str(playbook_path.resolve()),
    )
    logger.debug("Run ansible-playbook command: %s", cmd)

    return subprocess.run(
        cmd,
        env=env,
        cwd=ws_dir,
        check=False,
        encoding="utf8",
        capture_output=capture_output,
    )


def _run_single_test(
    test_case_path: Path,
    extra_roles_path: list[str] | None = None,
    extra_args: list[str] | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    raw_test = yaml.safe_load(test_case_path.read_text())[ROLY_TEST_CONFIG_KEY]
    test_case = TestCaseInputConfig.model_validate(raw_test)

    with tempfile.TemporaryDirectory() as raw_tmp_dir:
        ws_dir = Path(raw_tmp_dir).resolve()
        ansible_cfg_path = ws_dir / "ansible.cfg"
        make_roly_ansible_config(
            output_path=ansible_cfg_path, roles_path=extra_roles_path
        )
        logger.debug("Ansible config: %s", ansible_cfg_path.read_text())

        if test_case.tasks:
            # Create a tmp playbook and assign it back
            test_playbook_path = ws_dir / f"{test_case_path.stem}_playbook.yaml"
            test_playbook_path.write_text(
                yaml.dump(_make_content_playbook(test_case.tasks))
            )

            return _run_ansible_playbook(
                ws_dir=ws_dir,
                playbook_path=test_playbook_path,
                roly_test_case_path=test_case_path,
                ansible_cfg_path=ansible_cfg_path,
                extra_args=extra_args,
                capture_output=capture_output,
            )

    raise NotImplementedError


def _run_test(
    test_case_file_name: str, search_str: str, is_passed: bool = True
) -> None:
    result = _run_single_test(TEST_PLAYBOOK_BASE_DIR / test_case_file_name)

    msgs = []
    if is_passed and result.returncode:
        msgs.append(f"Return code is {result.returncode}. Expected: 0")
    if search_str not in result.stdout:
        msgs.append(f"Can not found the string in stdout. str: '{search_str}'")

    if msgs:
        msg = "\n".join(
            (
                f"Test file failed: {test_case_file_name}",
                *msgs,
                result.stdout,
                result.stderr,
            )
        )
        raise AssertionError(msg)


def _list_test_cases(
    base_dir: Path,
    config_key: str = "ROLY_INTERNAL_INTEGRATION_TEST_CONFIG",
) -> list[tuple[str, str, bool]]:
    test_paths = [
        path
        for path in base_dir.iterdir()
        if path.is_file() and path.name.startswith("test") and path.suffix == ".yaml"
    ]

    test_cases = []
    for path in test_paths:
        with path.open() as fin:
            raw_config = yaml.safe_load(fin)
            if test_config := raw_config.get(config_key, None):
                test_cases.append(
                    (
                        path.name,
                        test_config["search_keyword"],
                        test_config.get("is_passed", True),
                    )
                )

    return sorted(test_cases, key=lambda k: k[0])


@pytest.mark.integration
@pytest.mark.parametrize(
    ("test_case_file_name", "search_str", "is_pass"),
    _list_test_cases(TEST_PLAYBOOK_BASE_DIR),
)
def test_roly_callback(
    test_case_file_name: str, search_str: str, is_pass: bool
) -> None:
    _run_test(test_case_file_name, search_str, is_pass)
