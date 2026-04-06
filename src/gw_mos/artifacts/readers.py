from __future__ import annotations

from pathlib import Path

from gw_mos.utils.json_io import load_json


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict:
    return load_json(path)
