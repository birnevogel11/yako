from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from yako.ansible import make_yako_ansible_config
from yako.consts import YAKO_TEST_CONFIG_KEY
from yako.test_case import TestCaseInputConfig

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
    yako_test_case_path: Path,
    ansible_cfg_path: Path,
    yako_workspace_dir: Path,
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
            "-e",
            f"yako_workspace_dir={yako_workspace_dir}",
            "--inventory",
            "127.0.0.1,",
            "--limit",
            "127.0.0.1",
            "-e",
            f"@{yako_test_case_path.resolve()}",
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


def run_plugin_callback_test(
    test_case_path: Path,
    extra_roles_path: list[str] | None = None,
    extra_args: list[str] | None = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    raw_test = yaml.safe_load(test_case_path.read_text())[YAKO_TEST_CONFIG_KEY]
    test_case = TestCaseInputConfig.model_validate(raw_test)

    with tempfile.TemporaryDirectory() as raw_tmp_dir:
        ws_dir = Path(raw_tmp_dir).resolve()
        ansible_cfg_path = ws_dir / "ansible.cfg"
        make_yako_ansible_config(
            output_path=ansible_cfg_path, roles_path=extra_roles_path
        )
        logger.debug("Ansible config:\n%s", ansible_cfg_path.read_text())

        if test_case.tasks:
            # Create a tmp playbook and assign it back
            test_playbook_path = ws_dir / f"{test_case_path.stem}_playbook.yaml"
            test_playbook_path.write_text(
                yaml.dump(_make_content_playbook(test_case.tasks))
            )

            return _run_ansible_playbook(
                ws_dir=ws_dir,
                playbook_path=test_playbook_path,
                yako_test_case_path=test_case_path,
                yako_workspace_dir=ws_dir,
                ansible_cfg_path=ansible_cfg_path,
                extra_args=extra_args,
                capture_output=capture_output,
            )

    raise NotImplementedError
