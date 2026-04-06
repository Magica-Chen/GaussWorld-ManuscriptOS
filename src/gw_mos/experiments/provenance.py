from __future__ import annotations

from pathlib import Path

from gw_mos.utils.json_io import load_json


def provenance_record(project_root: Path, run_id: str) -> dict[str, str]:
    registry = load_json(project_root / "04_experiments/results_registry.json")
    for item in registry.get("runs", []):
        if item.get("run_id") == run_id:
            return {
                "run_id": run_id,
                "status": item.get("status", "unknown"),
                "script": item.get("script", ""),
                "session_name": item.get("session_name", ""),
            }
    return {"run_id": run_id, "status": "missing", "script": "", "session_name": ""}
