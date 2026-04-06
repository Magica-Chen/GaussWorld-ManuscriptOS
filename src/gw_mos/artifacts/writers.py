from __future__ import annotations

from pathlib import Path

from gw_mos.utils.json_io import save_json


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, content: dict) -> None:
    save_json(path, content)
