from pathlib import Path

import pytest
from inline_snapshot import snapshot

from roly.ansible import make_ansible_playbook_cmd, make_roly_ansible_config
from roly.config import AnsiblePlaybookCommandConfig


@pytest.mark.parametrize(
    ("enable_roly_callback", "expected_config"),
    [
        (
            True,
            snapshot(
                """\
[defaults]
library = /no-such-dir/plugins/module
callback_plugins = /no-such-dir/plugins/callback
interpreter_python = /no-such/python3
callbacks_enabled = roly_callback

""",
            ),
        ),
        (
            False,
            snapshot(
                """\
[defaults]
library = /no-such-dir/plugins/module
callback_plugins = /no-such-dir/plugins/callback
interpreter_python = /no-such/python3

""",
            ),
        ),
    ],
)
def test_make_roly_ansible_config_write_file(
    tmp_path: Path, enable_roly_callback: bool, expected_config: str
) -> None:
    ansible_config_path = tmp_path / "test_ansible.cfg"

    make_roly_ansible_config(
        enable_roly_callback=enable_roly_callback,
        base_dir=Path("/no-such-dir"),
        python_bin="/no-such/python3",
        output_path=ansible_config_path,
    )

    assert ansible_config_path.read_text() == expected_config


def test_make_roly_ansible_config_with_roles_path() -> None:
    config = make_roly_ansible_config(roles_path=["/path/to/role1", "/path/to/role2"])

    assert config["defaults"]["roles_path"] == snapshot("/path/to/role1:/path/to/role2")


def test_make_roly_ansible_config_with_playbook_dir() -> None:
    config = make_roly_ansible_config(playbook_dir=Path("/path/to/playbooks"))

    assert config["defaults"]["playbook_dir"] == snapshot("/path/to/playbooks")


@pytest.mark.parametrize(
    ("cmd_config", "expected_value"),
    [
        (
            AnsiblePlaybookCommandConfig(),
            snapshot(
                (
                    [
                        "/fake/ansible-playbook",
                        "--verbose",
                        "--connection=local",
                        "--inventory",
                        "127.0.0.1,",
                        "--limit",
                        "127.0.0.1",
                        "-e",
                        "roly_workspace_dir=/fake-ws",
                        "-e",
                        "@/fake/test-case.yaml",
                        "/fake/playbook.yaml",
                    ],
                    {
                        "ANSIBLE_CONFIG": "/fake-ws/ansible.cfg",
                        "ANSIBLE_STDOUT_CALLBACK": "debug",
                    },
                )
            ),
        ),
        (
            AnsiblePlaybookCommandConfig(
                connection="other",
                inventory="fake-inventory",
                limit="some-host",
                extra_args=["-e", "fake=fake"],
            ),
            snapshot(
                (
                    [
                        "/fake/ansible-playbook",
                        "--verbose",
                        "--connection=other",
                        "--inventory",
                        "fake-inventory",
                        "--limit",
                        "some-host",
                        "-e",
                        "roly_workspace_dir=/fake-ws",
                        "-e",
                        "@/fake/test-case.yaml",
                        "-e",
                        "fake=fake",
                        "/fake/playbook.yaml",
                    ],
                    {
                        "ANSIBLE_CONFIG": "/fake-ws/ansible.cfg",
                        "ANSIBLE_STDOUT_CALLBACK": "debug",
                    },
                )
            ),
        ),
    ],
)
def test_make_ansible_playbook_cmd(
    cmd_config: AnsiblePlaybookCommandConfig,
    expected_value: tuple[list[str], dict[str, str]],
) -> None:
    assert (
        make_ansible_playbook_cmd(
            ansible_playbook_bin="/fake/ansible-playbook",
            ansible_cfg_path="/fake-ws/ansible.cfg",
            cmd_config=cmd_config,
            roly_workspace_dir="/fake-ws",
            roly_test_case_path="/fake/test-case.yaml",
            playbook_path=[Path("/fake/playbook.yaml")],
        )
        == expected_value
    )
