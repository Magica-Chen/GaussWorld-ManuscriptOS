from __future__ import annotations

from pathlib import Path

import yaml

from gw_mos.agent_runtime import complete_with_openai
from gw_mos.artifacts.models import CitationRecord, PaperSpec
from gw_mos.utils.json_io import load_json


def novelty_risk_flags(spec: PaperSpec, citations: list[CitationRecord]) -> list[str]:
    flags: list[str] = []
    grounded = [citation for citation in citations if citation.verified]
    provisional = [citation for citation in citations if not citation.verified]

    if not grounded:
        flags.append("missing_canonical_literature")
    if provisional:
        flags.append("unverified_local_sources")
    if len(grounded) < 3:
        flags.append("thin_literature_base")

    keywords = _spec_keywords(spec)
    if grounded and keywords:
        overlap = 0
        for citation in grounded:
            title_tokens = set(_tokenize(citation.title))
            if title_tokens & keywords:
                overlap += 1
        if overlap == 0:
            flags.append("weak_keyword_overlap")
    return flags


def render_novelty_map(project_root: Path) -> str:
    spec = PaperSpec.model_validate(yaml.safe_load((project_root / "01_spec/paper_spec.yaml").read_text(encoding="utf-8")))
    data = load_json(project_root / "02_literature/citation_index.json")
    citations = [CitationRecord.model_validate(item) for item in data.get("papers", [])]
    grounded = [citation for citation in citations if citation.verified]
    provisional = [citation for citation in citations if not citation.verified]
    flags = novelty_risk_flags(spec, citations)

    lines = [
        "# Novelty Map",
        "",
        f"- Working title: `{spec.title_working or 'Untitled'}`",
        f"- Grounded references: `{len(grounded)}`",
        f"- Provisional local sources: `{len(provisional)}`",
        "",
        "## Closest Grounded Sources",
    ]
    if grounded:
        for citation in sorted(grounded, key=_citation_sort_key):
            source = citation.source_url or citation.source_type
            year = citation.year or "unknown"
            lines.append(f"- `{citation.bibtex_key or citation.id}` ({year}) {citation.title} [{source}]")
    else:
        lines.append("- None yet. Add grounded BibTeX entries with DOI, arXiv, or URL metadata.")

    lines.extend(["", "## Provisional Sources"])
    if provisional:
        for citation in sorted(provisional, key=_citation_sort_key):
            source = citation.source_url or citation.source_type
            year = citation.year or "unknown"
            lines.append(f"- `{citation.bibtex_key or citation.id}` ({year}) {citation.title} [{source}]")
    else:
        lines.append("- None.")

    lines.extend(["", "## Risk Flags"])
    if flags:
        lines.extend(f"- {flag}" for flag in flags)
    else:
        lines.append("- No obvious literature-ingestion risk flags from local metadata.")

    agent_summary = _agent_novelty_summary(project_root, spec, grounded)
    if agent_summary:
        lines.extend(["", "## Agent Assessment", agent_summary.strip()])

    lines.extend(
        [
            "",
            "## Notes",
            "- This map is generated from local ingested sources and any public metadata search results already imported into the workspace.",
            "- Prefer BibTeX or LaTeX-based references when possible; local PDFs are treated as provisional inputs.",
        ]
    )
    return "\n".join(lines) + "\n"


def _spec_keywords(spec: PaperSpec) -> set[str]:
    return set(_tokenize(" ".join([spec.title_working, spec.problem_statement])))


def _tokenize(text: str) -> list[str]:
    return [token for token in "".join(char.lower() if char.isalnum() else " " for char in text).split() if len(token) > 3]


def _citation_sort_key(citation: CitationRecord) -> tuple[int, str]:
    year = citation.year or 0
    return (-year, citation.title.lower())


def _agent_novelty_summary(project_root: Path, spec: PaperSpec, grounded: list[CitationRecord]) -> str:
    if not grounded:
        return ""
    citations_block = "\n".join(
        f"- {citation.title} ({citation.year or 'unknown'}) [{citation.source_url or citation.source_type}]"
        for citation in grounded[:8]
    )
    return complete_with_openai(
        project_root=project_root,
        prompt_path="agents/literature.md",
        prompt=(
            f"Working title: {spec.title_working}\n"
            f"Problem statement: {spec.problem_statement}\n"
            "Grounded references:\n"
            f"{citations_block}"
        ),
        fallback="",
        max_output_tokens=500,
    )
