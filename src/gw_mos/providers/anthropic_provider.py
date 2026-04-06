from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gw_mos.auth.service import AuthError, resolve_profile
from gw_mos.config import ANTHROPIC_API_VERSION, ANTHROPIC_MESSAGES_API_URL, DEFAULT_ANTHROPIC_MODEL
from gw_mos.providers.base import BaseProvider, ProviderAuthError, ProviderError, ProviderRequest, ProviderResponse


class AnthropicProvider(BaseProvider):
    name = "anthropic"

    def __init__(self, profile_id: str | None = None, start: Path | None = None) -> None:
        self.profile_id = profile_id
        self.start = start

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        try:
            profile = resolve_profile(provider=self.name, profile_id=self.profile_id, start=self.start)
        except AuthError as exc:
            raise ProviderAuthError(str(exc)) from exc
        if profile is None or not profile.api_key:
            raise ProviderAuthError("No Anthropic API key profile or environment credentials are configured.")

        payload = {
            "model": request.model or profile.model or DEFAULT_ANTHROPIC_MODEL,
            "max_tokens": request.max_output_tokens or 1200,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        raw = self._post_json(
            url=profile.base_url or ANTHROPIC_MESSAGES_API_URL,
            payload=payload,
            api_key=profile.api_key,
        )
        return ProviderResponse(
            provider=self.name,
            model=payload["model"],
            content=self._extract_text(raw),
            raw=raw,
        )

    def _post_json(self, url: str, payload: dict, api_key: str) -> dict:
        request = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
        request.add_header("x-api-key", api_key)
        request.add_header("anthropic-version", ANTHROPIC_API_VERSION)
        request.add_header("content-type", "application/json")
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Anthropic request failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise ProviderError(f"Anthropic request failed: {exc.reason}") from exc

    def _extract_text(self, payload: dict) -> str:
        parts: list[str] = []
        for item in payload.get("content", []):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
        if parts:
            return "\n".join(parts).strip()
        raise ProviderError("Anthropic response did not contain text output.")
