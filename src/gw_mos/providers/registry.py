from __future__ import annotations

from pathlib import Path

from gw_mos.auth.service import AuthError, resolve_profile
from gw_mos.providers.anthropic_provider import AnthropicProvider
from gw_mos.providers.base import BaseProvider
from gw_mos.providers.openai_provider import OpenAIProvider


def build_provider(name: str, *, profile_id: str | None = None, start: Path | None = None) -> BaseProvider:
    if name == "openai":
        return OpenAIProvider(profile_id=profile_id, start=start)
    if name == "anthropic":
        return AnthropicProvider(profile_id=profile_id, start=start)
    raise ValueError(f"Unsupported provider: {name}")


def provider_available(name: str, *, profile_id: str | None = None, start: Path | None = None) -> bool:
    try:
        return resolve_profile(provider=name, profile_id=profile_id, start=start) is not None
    except AuthError:
        return False
