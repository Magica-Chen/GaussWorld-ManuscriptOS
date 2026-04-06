from __future__ import annotations

from pathlib import Path

from gw_mos.experiments.runner_tmux import TmuxRunner


def experiment_status_summary(project_root: Path) -> dict[str, str]:
    runner = TmuxRunner()
    return runner.sync_status(project_root)
