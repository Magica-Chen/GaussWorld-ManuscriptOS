from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Mapping


def run_command(
    args: list[str],
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> CompletedProcess[str]:
    return run(args, check=False, text=True, capture_output=True, cwd=cwd, env=env)
