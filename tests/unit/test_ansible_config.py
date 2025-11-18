import io
from pathlib import Path

from inline_snapshot import snapshot

from roly.ansible_config import make_roly_ansible_config


def test_make_roly_ansible_config() -> None:
    config = make_roly_ansible_config(base_dir=Path("/no-such-dir"), python_bin="/no-such/python3")

    io_string = io.StringIO()
    config.write(io_string)
    content = io_string.getvalue()

    assert content == snapshot(
        """\
[DEFAULT]
library = /no-such-dir/plugins/module
callback_plugins = /no-such-dir/plugins/callback
interpreter_python = /no-such/python3
callback_enabled = roly_callback

""",
    )
