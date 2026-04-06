from __future__ import annotations

from pathlib import Path

from gw_mos.artifacts.models import ProjectState, RuntimeStatus
from gw_mos.utils.json_io import load_json, save_json


class StateStore:
    def load_state(self, project_root: Path) -> ProjectState:
        data = load_json(project_root / "runtime/state.json")
        return ProjectState.model_validate(data)

    def save_state(self, project_root: Path, state: ProjectState) -> None:
        save_json(project_root / "runtime/state.json", state.model_dump(mode="json"))

    def load_status(self, project_root: Path) -> RuntimeStatus:
        data = load_json(project_root / "runtime/status.json")
        return RuntimeStatus.model_validate(data)

    def save_status(self, project_root: Path, status: RuntimeStatus) -> None:
        save_json(project_root / "runtime/status.json", status.model_dump(mode="json"))
