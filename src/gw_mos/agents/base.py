from __future__ import annotations

from pydantic import BaseModel, Field


class AgentContract(BaseModel):
    name: str
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)
    escalation_conditions: list[str] = Field(default_factory=list)
