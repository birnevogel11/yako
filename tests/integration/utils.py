import shutil
import subprocess
import tempfile
from pathlib import Path

from roly.ansible_config import make_roly_ansible_config


def run_ansible_playbook(playbook_path: Path, roly_test_case_path: Path) -> subprocess.CompletedProcess[str]:
    if not (bin_path := shutil.which("ansible-playbook")):
        raise RuntimeError("ansible-playbook is unavailable.")
    ansible_playbook_bin = Path(bin_path).resolve()

    with tempfile.TemporaryDirectory() as raw_tmp_dir:
        tmp_dir = Path(raw_tmp_dir).resolve()
        ansible_cfg_path = tmp_dir / "ansible.cfg"
        make_roly_ansible_config(output_path=ansible_cfg_path)

        env = {
            "ANSIBLE_CFG": str(ansible_cfg_path.resolve()),
            "ANSIBLE_STDOUT_CALLBACK": "debug",
        }
        cmd = [
            str(ansible_playbook_bin.resolve()),
            "-v",
            "--connection=local",
            "--inventory",
            "127.0.0.1,",
            "--limit",
            "127.0.0.1",
            "-e",
            f"@{roly_test_case_path.resolve()}",
            str(playbook_path.resolve()),
        ]
        print(" ".join(cmd))

        return subprocess.run(cmd, env=env, cwd=tmp_dir, check=False, encoding="utf8", capture_output=True)
