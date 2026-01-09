from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, NewType, cast

import yaml

from roly.ansible import make_ansible_playbook_cmd, make_roly_ansible_config
from roly.resolve import resolve_roles_path
from roly.runner.utils import run_command
from roly.test_case import make_content_playbook

if TYPE_CHECKING:
    import subprocess
    from collections.abc import Iterable

    from roly.config import DockerRunnerConfig, RolyConfig
    from roly.test_case import TestCase


logger = logging.getLogger(__name__)

ContainerPath = NewType("ContainerPath", Path)


def _get_all_playbook_dirs(config: RolyConfig) -> list[Path]:
    base_dirs = [
        (
            path.expanduser().resolve()
            if path.is_dir()
            else path.parent.expanduser().resolve()
        )
        for path in config.base_dir
    ]
    return sorted({*base_dirs, Path.cwd()})


def _create_mount_mapping(
    host_path: Iterable[Path], container_prefix: Path = Path("/host_roly")
) -> dict[Path, ContainerPath]:
    return {
        path.resolve(): ContainerPath(container_prefix / str(path.resolve())[1:])
        for path in host_path
    }


def _create_container_ansible_config(
    output_base_dir: Path,
    config: DockerRunnerConfig,
    roles_ct_path: list[ContainerPath],
) -> Path:
    cfg_path = output_base_dir / "ansible.cfg"

    make_roly_ansible_config(
        base_dir=config.roly_src_dir,
        python_bin=str(config.roly_venv_dir / "bin" / "python"),
        roles_path=[str(path) for path in roles_ct_path],
        output_path=cfg_path,
    )

    return cfg_path


def _remap_playbook_path(
    case: TestCase, playbook_ct_dirs: dict[Path, ContainerPath]
) -> TestCase:
    if not case.playbooks:
        return case

    ct_path = []
    for path in case.playbooks:
        for base, ct_base in playbook_ct_dirs.items():
            if path.is_relative_to(base):
                ct_path.append(ct_base / path.relative_to(base))

    return case.model_copy(update={"playbooks": ct_path})


def _create_ct_playbook(case: TestCase, ws_dir: Path, ws_ct_dir: Path) -> TestCase:
    playbook_path = ws_dir / "test_case_playbook.yaml"
    playbook_ct_path = ws_ct_dir / playbook_path.name

    playbook_path.write_text(yaml.dump(make_content_playbook(case.tasks)))

    return case.model_copy(update={"playbooks": [playbook_ct_path], "tasks": []})


def _convert_test_case_playbook(
    case: TestCase,
    ws_dir: Path,
    ws_ct_dir: Path,
    playbook_ct_dirs: dict[Path, ContainerPath],
) -> TestCase:
    return (
        _remap_playbook_path(case, playbook_ct_dirs)
        if case.playbooks
        else _create_ct_playbook(case, ws_dir, ws_ct_dir)
    )


def _make_docker_cmd(
    ansible_cmd: list[str],
    ansible_cmd_env: dict[str, str],
    docker_config: DockerRunnerConfig,
    mount_mapping: dict[Path, ContainerPath],
) -> list[str]:
    cmd = ["docker", "container", "run", "--rm"]

    for name, value in ansible_cmd_env.items():
        cmd.extend(("-e", f"{name}={value}"))

    for path, ct_path in mount_mapping.items():
        cmd.extend(("-v", f"{path}:{ct_path}"))

    if docker_config.host_roly_src_dir:
        cmd.extend(("-v", f"{docker_config.host_roly_src_dir}:/home/ubuntu/roly"))

    cmd.extend(
        (
            "-w",
            str(docker_config.workspace_dir),
            *docker_config.extra_args,
            docker_config.image_name,
            *ansible_cmd,
        )
    )

    return cmd


class DockerTestCaseRunner:
    def __init__(self, config: RolyConfig) -> None:
        self._config = config
        self._base_mount_mappings: dict[Path, ContainerPath] = {}
        self._ansible_cfg_path: Path = None  # type: ignore[assignment]
        self._ansible_cfg_ct_path: ContainerPath = None  # type: ignore[assignment]
        self._playbook_ct_dirs: dict[Path, ContainerPath] = {}

    def _update_internal_path_state(self, ansible_cfg_path: Path) -> None:
        self._ansible_cfg_path = ansible_cfg_path
        self._base_mount_mappings[self._ansible_cfg_path.parent] = ContainerPath(
            Path("/host_roly_base")
        )
        self._ansible_cfg_ct_path = (
            self._base_mount_mappings[self._ansible_cfg_path.parent]
            / self._ansible_cfg_path.name
        )
        self._playbook_ct_dirs = _create_mount_mapping(
            _get_all_playbook_dirs(self._config)
        )

    def init(self, base_dir: Path) -> None:
        roles_path = resolve_roles_path(self._config.ansible)
        roles_ct_path = _create_mount_mapping(roles_path)

        playbook_ct_dirs = _create_mount_mapping(_get_all_playbook_dirs(self._config))

        self._base_mount_mappings = {**roles_ct_path, **playbook_ct_dirs}

        ansible_cfg_path = _create_container_ansible_config(
            base_dir,
            self._config.runner.docker,
            [roles_ct_path[path] for path in roles_path],
        )
        logger.debug("Ansible config content:\n%s", ansible_cfg_path.read_text())
        self._update_internal_path_state(ansible_cfg_path)

    def run(self, case: TestCase) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as raw_ws_dir:
            ws_dir = Path(raw_ws_dir)

            runner_config = self._config.runner.docker
            ws_ct_dir = runner_config.workspace_dir

            case = _convert_test_case_playbook(
                case, ws_dir, ws_ct_dir, self._playbook_ct_dirs
            )

            roly_test_case_path = ws_dir / "test_case.yaml"
            case.dump_roly_callback_config_file(roly_test_case_path)

            ansible_cmd, ansible_cmd_env = make_ansible_playbook_cmd(
                ansible_playbook_bin=runner_config.ansible_playbook_bin,
                ansible_cfg_path=self._ansible_cfg_ct_path,
                cmd_config=self._config.ansible.ansible_playbook,
                roly_test_case_path=ws_ct_dir / roly_test_case_path.name,
                roly_workspace_dir=ws_ct_dir,
                playbook_path=case.playbooks,
            )
            docker_cmd = _make_docker_cmd(
                ansible_cmd,
                ansible_cmd_env,
                runner_config,
                cast(
                    "dict[Path, ContainerPath]",
                    {
                        **self._base_mount_mappings,
                        ws_dir: ws_ct_dir,
                    },
                ),
            )
            logger.debug(
                "Run command. test_case: %s, cmd: %s",
                case.display_name,
                docker_cmd,
            )

            return run_command(docker_cmd)
