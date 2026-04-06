from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from gw_mos.auth.service import AuthError, resolve_profile
from gw_mos.config import DEFAULT_OPENAI_MODEL, OPENAI_RESPONSES_API_URL
from gw_mos.providers.base import BaseProvider, ProviderAuthError, ProviderError, ProviderRequest, ProviderResponse


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, profile_id: str | None = None, start: Path | None = None) -> None:
        self.profile_id = profile_id
        self.start = start

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        try:
            profile = resolve_profile(provider=self.name, profile_id=self.profile_id, start=self.start)
        except AuthError as exc:
            raise ProviderAuthError(str(exc)) from exc
        if profile is None:
            raise ProviderAuthError("No OpenAI profile or environment credentials are configured.")
        token = profile.api_key or profile.access_token
        if not token:
            raise ProviderAuthError("OpenAI profile does not contain an API key or access token.")

        payload = {
            "model": request.model or profile.model or DEFAULT_OPENAI_MODEL,
            "input": self._build_input(request),
        }
        if request.max_output_tokens is not None:
            payload["max_output_tokens"] = request.max_output_tokens
        raw = self._post_json(
            url=profile.base_url or OPENAI_RESPONSES_API_URL,
            payload=payload,
            token=token,
            profile=profile,
        )
        return ProviderResponse(
            provider=self.name,
            model=payload["model"],
            content=self._extract_text(raw),
            raw=raw,
        )

    def _build_input(self, request: ProviderRequest) -> list[dict]:
        messages: list[dict] = []
        if request.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": request.system_prompt}],
                }
            )
        messages.append(
            {
                "role": "user",
                "content": [{"type": "input_text", "text": request.prompt}],
            }
        )
        return messages

    def _post_json(self, url: str, payload: dict, token: str, profile: object) -> dict:
        request = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Content-Type", "application/json")
        if getattr(profile, "organization", None):
            request.add_header("OpenAI-Organization", profile.organization)
        if getattr(profile, "project", None):
            request.add_header("OpenAI-Project", profile.project)
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"OpenAI request failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise ProviderError(f"OpenAI request failed: {exc.reason}") from exc

    def _extract_text(self, payload: dict) -> str:
        if isinstance(payload.get("output_text"), str) and payload["output_text"]:
            return payload["output_text"]
        parts: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()
        raise ProviderError("OpenAI response did not contain text output.")
