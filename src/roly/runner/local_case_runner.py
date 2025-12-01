from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from roly.ansible import make_ansible_playbook_cmd, make_roly_ansible_config
from roly.resolve import resolve_roles_path
from roly.runner.utils import run_command
from roly.test_case import make_content_playbook

if TYPE_CHECKING:
    import subprocess

    from roly.config import RolyConfig
    from roly.test_case import TestCase

logger = logging.getLogger(__name__)


def _search_ansible_playbook() -> Path:
    bin_path = Path(sys.executable).parent / "ansible-playbook"
    if bin_path.exists():
        return bin_path

    if default_bin_path := shutil.which("ansible-playbook"):
        return Path(default_bin_path)

    raise RuntimeError("ansible-playbook not found!")


def _create_local_ansible_config(
    output_base_dir: Path,
    roles_ct_path: list[Path],
    ansible_playbook_bin: Path,
) -> Path:
    make_roly_ansible_config(
        python_bin=str(ansible_playbook_bin),
        roles_path=[str(path) for path in roles_ct_path],
        output_path=output_base_dir / "ansible.cfg",
    )

    return output_base_dir / "ansible.cfg"


def _create_playbook_from_tasks(case: TestCase, ws_dir: Path) -> TestCase:
    playbook_path = ws_dir / "test_case_playbook.yaml"
    playbook_path.write_text(yaml.dump(make_content_playbook(case.tasks)))
    return case.model_copy(update={"playbooks": [playbook_path], "tasks": []})


class LocalTestCaseRunner:
    def __init__(self, config: RolyConfig) -> None:
        self._config = config
        self._ansible_cfg_path: Path = None  # type: ignore[assignment]
        self._ansible_playbook_bin: Path = None  # type: ignore[assignment]

    def _update_internal_path_state(
        self, ansible_cfg_path: Path, ansible_playbook_bin: Path
    ) -> None:
        self._ansible_cfg_path = ansible_cfg_path
        self._ansible_playbook_bin = ansible_playbook_bin

    def init(self, base_dir: Path) -> None:
        roles_path = resolve_roles_path(self._config.ansible)
        ansible_playbook_bin = _search_ansible_playbook()
        ansible_cfg_path = _create_local_ansible_config(
            base_dir, roles_path, ansible_playbook_bin
        )

        self._update_internal_path_state(ansible_cfg_path, ansible_playbook_bin)

    def run(self, case: TestCase) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as raw_ws_dir:
            ws_dir = Path(raw_ws_dir)

            if case.tasks:
                case = _create_playbook_from_tasks(case, ws_dir)

            roly_test_case_path = ws_dir / "test_case.yaml"
            case.dump_roly_callback_config_file(roly_test_case_path)

            cmd, env = make_ansible_playbook_cmd(
                ansible_playbook_bin=self._ansible_playbook_bin,
                ansible_cfg_path=self._ansible_cfg_path,
                cmd_config=self._config.ansible.ansible_playbook,
                playbook_path=case.playbooks,
                roly_test_case_path=roly_test_case_path,
                roly_workspace_dir=ws_dir,
            )

            return run_command(cmd=cmd, env=env)
