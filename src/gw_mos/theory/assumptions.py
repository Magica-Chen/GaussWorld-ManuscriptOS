from __future__ import annotations

from gw_mos.artifacts.models import PaperSpec


def assumption_checklist() -> list[str]:
    return ["domain", "identifiability", "regularity", "boundary_conditions"]


def normalized_assumptions(spec: PaperSpec) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in spec.assumptions:
        cleaned = " ".join(item.strip().split())
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(cleaned)
    return ordered


def missing_assumption_topics(spec: PaperSpec) -> list[str]:
    assumptions_text = " ".join(normalized_assumptions(spec)).lower()
    missing: list[str] = []
    for topic in assumption_checklist():
        tokens = topic.replace("_", " ").split()
        if not any(token in assumptions_text for token in tokens):
            missing.append(topic)
    return missing
