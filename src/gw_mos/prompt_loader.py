from __future__ import annotations

from pathlib import Path

from gw_mos.config import resolve_app_home


def load_prompt(relative_path: str, fallback: str = "") -> str:
    prompt_path = resolve_app_home() / "prompts" / relative_path
    if not prompt_path.exists():
        return fallback
    return prompt_path.read_text(encoding="utf-8")


def prompt_path(relative_path: str) -> Path:
    return resolve_app_home() / "prompts" / relative_path
