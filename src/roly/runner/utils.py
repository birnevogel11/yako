from __future__ import annotations

import subprocess


def run_command(
    cmd: list[str], env: dict[str, str] | None = None, capture_output: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, env=env, check=False, capture_output=capture_output, encoding="utf-8"
    )
