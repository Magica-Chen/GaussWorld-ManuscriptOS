from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderRequest(BaseModel):
    prompt: str
    system_prompt: str = ""
    model: str | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ProviderResponse(BaseModel):
    provider: str
    content: str
    model: str = ""
    raw: dict = Field(default_factory=dict)


class ProviderError(RuntimeError):
    pass


class ProviderAuthError(ProviderError):
    pass


class BaseProvider:
    name = "base"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError
