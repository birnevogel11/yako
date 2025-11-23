import configparser
import sys
from pathlib import Path


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
        "interpreter_python": str(Path(python_bin or sys.executable)),
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
