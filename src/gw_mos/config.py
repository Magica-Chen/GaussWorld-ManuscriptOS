from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "gw-mos"
DEFAULT_WORKSPACE_ROOT = Path.cwd()
RUNTIME_STATE_FILE = "runtime/state.json"
RUNTIME_STATUS_FILE = "runtime/status.json"
RUNTIME_TMUX_FILE = "runtime/tmux_jobs.json"
AUTH_PROFILES_FILE = "auth/profiles.json"
DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
OPENAI_RESPONSES_API_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


def resolve_app_home(start: Path | None = None) -> Path:
    env_home = os.environ.get("GW_MOS_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src/gw_mos").exists():
            return candidate
    return current


def resolve_app_file(relative_path: str, start: Path | None = None) -> Path:
    return resolve_app_home(start=start) / relative_path
