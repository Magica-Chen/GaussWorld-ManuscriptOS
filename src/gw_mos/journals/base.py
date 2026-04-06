from __future__ import annotations

from pydantic import BaseModel


class JournalProfile(BaseModel):
    family: str
    scope_summary: str
    template_hint: str
