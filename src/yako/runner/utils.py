from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import subprocess
    import types
    from typing import Self


import subprocess


def run_command(
    cmd: list[str], env: dict[str, str] | None = None, capture_output: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, env=env, check=False, capture_output=capture_output, encoding="utf-8"
    )


class Timer:
    def __init__(self) -> None:
        self.start_time: float | None = None
        self.elapsed_time: float | None = None

    def __enter__(self) -> Self:
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        if self.start_time is not None:
            self.elapsed_time = time.time() - self.start_time
