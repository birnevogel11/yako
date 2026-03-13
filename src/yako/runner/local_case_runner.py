from __future__ import annotations

import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from yako.ansible import make_ansible_playbook_cmd, make_yako_ansible_config
from yako.resolve import resolve_roles_path
from yako.runner.utils import run_command
from yako.test_case import make_content_playbook
from yako.yaml import safe_dump

if TYPE_CHECKING:
    import subprocess

    from yako.config import YakoConfig
    from yako.test_case import TestCase

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
    python_bin: Path | None = None,
) -> Path:
    make_yako_ansible_config(
        python_bin=str(python_bin) if python_bin else None,
        roles_path=[str(path) for path in roles_ct_path],
        output_path=output_base_dir / "ansible.cfg",
    )

    return output_base_dir / "ansible.cfg"


def _create_playbook_from_tasks(case: TestCase, ws_dir: Path) -> TestCase:
    playbook_path = ws_dir / "test_case_playbook.yaml"
    content = make_content_playbook(case.tasks)
    playbook_path.write_text(safe_dump(content))
    return case.model_copy(update={"playbooks": [playbook_path], "tasks": []})


class LocalTestCaseRunner:
    def __init__(self, config: YakoConfig) -> None:
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
        ansible_cfg_path = _create_local_ansible_config(base_dir, roles_path)

        logger.debug("Ansible config content:\n%s", ansible_cfg_path.read_text())

        self._update_internal_path_state(ansible_cfg_path, ansible_playbook_bin)

    def run(self, case: TestCase) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as raw_ws_dir:
            ws_dir = Path(raw_ws_dir)

            if case.tasks:
                case = _create_playbook_from_tasks(case, ws_dir)

            yako_test_case_path = ws_dir / "test_case.yaml"
            case.dump_yako_callback_config_file(yako_test_case_path)

            cmd, env = make_ansible_playbook_cmd(
                ansible_playbook_bin=self._ansible_playbook_bin,
                ansible_cfg_path=self._ansible_cfg_path,
                cmd_config=self._config.ansible.ansible_playbook,
                playbook_path=case.playbooks,
                yako_test_case_path=yako_test_case_path,
                yako_workspace_dir=ws_dir,
                search_file_paths=[ws_dir, case.path.parent],
            )
            logger.debug(
                "Run command. test_case: %s, cmd: %s",
                case.display_name,
                cmd,
            )
            return run_command(cmd=cmd, env=env)
