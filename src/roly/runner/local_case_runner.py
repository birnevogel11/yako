from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from roly.ansible_config import make_roly_ansible_config
from roly.resolve import resolve_roles_path

if TYPE_CHECKING:
    import subprocess

    from roly.config import RolyConfig
    from roly.test_case import TestCase

logger = logging.getLogger(__name__)


def _search_ansible_playbook() -> Path | None:
    bin_path = Path(sys.executable).parent / "ansible-playbook"
    if bin_path.exists():
        return bin_path

    if default_bin_path := shutil.which("ansible-playbook"):
        return Path(default_bin_path)

    return None


def _create_local_ansible_config(
    output_base_dir: Path,
    roles_ct_path: list[Path],
) -> Path:
    ansible_playbook_bin = _search_ansible_playbook()
    if not ansible_playbook_bin:
        raise RuntimeError("ansible-playbook bin not found!")

    make_roly_ansible_config(
        python_bin=str(ansible_playbook_bin),
        roles_path=[str(path) for path in roles_ct_path],
        output_path=output_base_dir / "ansible.cfg",
    )

    return output_base_dir / "ansible.cfg"


class LocalTestCaseRunner:
    def __init__(self, config: RolyConfig) -> None:
        self._config = config
        self._ansible_cfg_path: Path = None  # type: ignore[assignment]

    def _update_internal_path_state(self, ansible_cfg_path: Path) -> None:
        self._ansible_cfg_path = ansible_cfg_path

    def init(self, base_dir: Path) -> None:
        roles_path = resolve_roles_path(self._config.ansible)
        ansible_cfg_path = _create_local_ansible_config(base_dir, roles_path)

        self._update_internal_path_state(ansible_cfg_path)

    def run(self, case: TestCase) -> subprocess.CompletedProcess[str]:
        raise NotImplementedError
