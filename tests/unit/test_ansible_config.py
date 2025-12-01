from pathlib import Path

import pytest
from inline_snapshot import snapshot

from roly.ansible import make_roly_ansible_config


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
