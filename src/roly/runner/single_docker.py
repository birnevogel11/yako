from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from roly.ansible_config import make_roly_ansible_config
from roly.consts import ROLY_TEST_CONFIG_KEY
from roly.runner.single_runner import _make_content_playbook
from roly.test_case import TestCaseInputConfig

logger = logging.getLogger(__name__)


def _make_ansible_playbook_cmd(
    *,
    ansible_playbook_bin: Path,
    playbook_path: Path,
    roly_test_case_path: Path,
    ansible_cfg_path: Path,
    extra_args: list[str] | None = None,
) -> tuple[tuple[str, ...], dict[str, str]]:
    env = {
        "ANSIBLE_CFG": str(ansible_cfg_path),
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
    return cmd, env


def run_single_test_docker(
    test_case_path: Path,
    show_stdout: bool = True,
    extra_roles_path: list[str] | None = None,
    capture_output: bool = True,
    roly_repo_path: Path | None = None,
    image_name: str = "bv11/roly",
) -> None:
    raw_test = yaml.safe_load(test_case_path.read_text())[ROLY_TEST_CONFIG_KEY]
    test_case = TestCaseInputConfig.model_validate(raw_test)

    docker_cmd = [
        "docker",
        "container",
        "run",
        "--rm",
        "-it",
        "--user",
        "1000:1000",
    ]
    if roly_repo_path:
        docker_cmd.extend(("-v", f"{roly_repo_path.resolve()}:/roly:ro"))

    with tempfile.TemporaryDirectory() as raw_tmp_dir:
        ws_dir = Path(raw_tmp_dir).resolve()
        ansible_cfg_path = ws_dir / "ansible.cfg"
        make_roly_ansible_config(
            output_path=ansible_cfg_path,
            extra_roles_path=extra_roles_path,
            base_dir=Path("/workspace"),
        )
        logger.debug("Ansible config: %s", ansible_cfg_path.read_text())
        shutil.copy(test_case_path, ws_dir / test_case_path.name)

        docker_cmd.extend(("-v", f"{ws_dir}:/workspace:rw", "-w", "/workspace"))

        if test_case.tasks:
            # Create a tmp playbook and assign it back
            test_playbook_path = ws_dir / f"{test_case_path.stem}_playbook.yaml"
            test_playbook_path.write_text(yaml.dump(_make_content_playbook(test_case.tasks)))

            # TODO: replace the test_case with a playbook path and empty content
            ansible_playbook_cmd, env = _make_ansible_playbook_cmd(
                ansible_playbook_bin=Path("/app/bin/ansible-playbook"),
                playbook_path=Path("/workspace") / test_playbook_path.name,
                roly_test_case_path=Path("/workspace") / test_case_path.name,
                ansible_cfg_path=Path("/workspace") / ansible_cfg_path.name,
            )
            for key, value in env.items():
                docker_cmd.extend(("-e", f"{key}={value}"))

            docker_cmd.append(image_name)
            docker_cmd.extend(ansible_playbook_cmd)

            print("docker command:", " ".join(docker_cmd))
            subprocess.run(docker_cmd, check=True)

        if test_case.playbooks:
            # TODO: implement it.
            raise NotImplementedError


def run_single_test_docker_cli(
    test_case_path: Path,
    show_stdout: bool = True,
    extra_roles_path: list[str] | None = None,
    capture_output: bool = True,
    image_name: str = "bv11/roly",
) -> None:
    run_single_test_docker(
        test_case_path,
        show_stdout=show_stdout,
        extra_roles_path=extra_roles_path,
        capture_output=capture_output,
        image_name=image_name,
    )
