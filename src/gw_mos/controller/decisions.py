from __future__ import annotations

from pydantic import BaseModel, Field


class ControllerDecision(BaseModel):
    accepted: bool = False
    rationale: str = ""
    blockers: list[str] = Field(default_factory=list)
