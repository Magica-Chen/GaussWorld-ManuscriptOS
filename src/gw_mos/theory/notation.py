from __future__ import annotations

import re

from gw_mos.artifacts.models import PaperSpec

MATH_TOKEN_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]{0,5}|[a-z](?:_[a-z0-9]+)?)\b")
STOPWORDS = {
    "we",
    "the",
    "and",
    "for",
    "with",
    "show",
    "prove",
    "under",
    "data",
    "noise",
    "study",
    "model",
}


def notation_report(spec: PaperSpec) -> dict[str, list[str]]:
    text = " ".join(
        [
            spec.title_working,
            spec.problem_statement,
            *(claim.text for claim in spec.core_claims),
            *spec.assumptions,
        ]
    )
    candidates = []
    for token in MATH_TOKEN_RE.findall(text):
        lowered = token.lower()
        if lowered in STOPWORDS or len(token) == 1 and token in {"a", "i"}:
            continue
        candidates.append(token)

    ordered = _dedupe(candidates)[:8]
    notes: list[str] = []
    if not ordered:
        notes.append("No math-like notation tokens were extracted from the current spec.")
    else:
        notes.append("Notation tokens were inferred heuristically from the current spec and should be formalized.")

    undefined = []
    if "X" in ordered and "Y" not in ordered and "signal" in text.lower():
        undefined.append("If X denotes an observation process, define the target or response variable explicitly.")

    return {
        "candidate_symbols": ordered,
        "collisions": [],
        "undefined_symbols": undefined,
        "notes": notes,
    }


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
