from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from gw_mos.prompt_loader import load_prompt
from gw_mos.providers.base import ProviderError, ProviderRequest
from gw_mos.providers.registry import build_provider, provider_available


def complete_with_openai(
    *,
    project_root: Path,
    prompt_path: str,
    prompt: str,
    fallback: str = "",
    max_output_tokens: int = 1200,
) -> str:
    if not provider_available("openai", start=project_root):
        return fallback
    provider = build_provider("openai", start=project_root)
    try:
        response = provider.generate(
            ProviderRequest(
                prompt=prompt,
                system_prompt=load_prompt(prompt_path, fallback="You are a research paper completion agent."),
                max_output_tokens=max_output_tokens,
            )
        )
    except ProviderError:
        return fallback
    return response.content.strip() or fallback


def complete_json_with_openai(
    *,
    project_root: Path,
    prompt_path: str,
    prompt: str,
    fallback: dict[str, Any] | None = None,
    max_output_tokens: int = 1200,
) -> dict[str, Any]:
    raw = complete_with_openai(
        project_root=project_root,
        prompt_path=prompt_path,
        prompt=prompt,
        fallback=json.dumps(fallback or {}),
        max_output_tokens=max_output_tokens,
    )
    payload = _extract_json_object(raw)
    if not payload:
        return fallback or {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return fallback or {}


def _extract_json_object(text: str) -> str | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    return match.group(0)
