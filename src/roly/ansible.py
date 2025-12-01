from __future__ import annotations

import configparser
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from roly.config import AnsiblePlaybookCommandConfig


def make_roly_ansible_config(
    enable_roly_callback: bool = True,
    *,
    base_dir: Path | None = None,
    python_bin: str | None = None,
    output_path: Path | None = None,
    roles_path: list[str] | None = None,
    playbook_dir: Path | None = None,
) -> configparser.ConfigParser:
    base_dir = base_dir or Path(__file__).parent.resolve()

    default_config = {
        "library": str(base_dir / "plugins" / "module"),
        "callback_plugins": str(base_dir / "plugins" / "callback"),
        "interpreter_python": python_bin or sys.executable,
    }
    if enable_roly_callback:
        default_config["callbacks_enabled"] = "roly_callback"
    if roles_path:
        default_config["roles_path"] = ":".join(roles_path)
    if playbook_dir:
        default_config["playbook_dir"] = str(playbook_dir.resolve())

    config = configparser.ConfigParser()
    config["defaults"] = default_config

    if output_path:
        output_path.parent.mkdir(exist_ok=True, parents=True)
        with output_path.open("w") as fout:
            config.write(fout)

    return config


def make_ansible_playbook_cmd(
    *,
    ansible_playbook_bin: Path,
    ansible_cfg_path: Path,
    cmd_config: AnsiblePlaybookCommandConfig,
    roly_workspace_dir: Path,
    roly_test_case_path: Path,
    playbook_path: list[Path],
) -> tuple[list[str], dict[str, str]]:
    env = {
        "ANSIBLE_CONFIG": str(ansible_cfg_path),
        "ANSIBLE_STDOUT_CALLBACK": cmd_config.ansible_stdout_callback,
    }
    cmd = [
        str(ansible_playbook_bin),
        "--verbose",
        f"--connection={cmd_config.connection}",
        "--inventory",
        f"{cmd_config.inventory}",
        "--limit",
        f"{cmd_config.limit}",
        "-e",
        f"roly_workspace_dir={roly_workspace_dir.resolve()}",
        "-e",
        f"@{roly_test_case_path.resolve()}",
        *(cmd_config.extra_args or ()),
        *(str(path) for path in playbook_path),
    ]

    return cmd, env
