from __future__ import annotations

import re
from pathlib import Path

import yaml

from gw_mos.agent_runtime import complete_json_with_openai
from gw_mos.artifacts.models import ClaimRecord, PaperSpec
from gw_mos.artifacts.readers import read_text
from gw_mos.artifacts.writers import write_text

HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*+]\s+(?P<item>.+?)\s*$")


def build_paper_spec(project_root: Path, journal_family: str, project_name: str) -> PaperSpec:
    idea_path = project_root / "00_intake/idea.md"
    constraints_path = project_root / "00_intake/constraints.md"
    journal_targets_path = project_root / "00_intake/journal_targets.md"

    idea_text = read_text(idea_path)
    constraints_text = read_text(constraints_path) if constraints_path.exists() else ""
    title, sections = _parse_markdown_sections(idea_text)
    full_text = "\n".join(line for lines in sections.values() for line in lines)

    target_journal = _extract_target_journal(journal_targets_path, journal_family)
    problem_statement = _extract_problem_statement(sections) or _first_non_heading_paragraph(idea_text)
    claims = _extract_claims(sections)
    assumptions = _extract_assumptions(sections)
    contribution_type = _infer_contribution_types(full_text)
    dataset_needs = _infer_dataset_needs(f"{full_text}\n{constraints_text}")

    if not claims and problem_statement:
        claims = [ClaimRecord(id="C1", text=f"Develop the main contribution implied by: {problem_statement}")]

    spec = PaperSpec(
        title_working=title or _humanize_project_name(project_name),
        problem_statement=problem_statement,
        contribution_type=contribution_type,
        target_journal=target_journal,
        journal_family=journal_family,
        core_claims=claims,
        assumptions=assumptions,
        dataset_needs=dataset_needs,
    )
    return _refine_spec_with_provider(
        project_root=project_root,
        spec=spec,
        idea_text=idea_text,
        constraints_text=constraints_text,
        target_journal=target_journal,
    )


def write_spec_outputs(project_root: Path, spec: PaperSpec) -> None:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    spec_path.write_text(yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False), encoding="utf-8")

    lines = [
        "# Contribution Hypotheses",
        "",
        "## Problem Statement",
        spec.problem_statement or "Not yet specified.",
        "",
        "## Core Claims",
    ]
    if spec.core_claims:
        lines.extend(f"- [{claim.id}] {claim.text}" for claim in spec.core_claims)
    else:
        lines.append("- None extracted yet.")
    lines.extend(["", "## Assumptions"])
    if spec.assumptions:
        lines.extend(f"- {assumption}" for assumption in spec.assumptions)
    else:
        lines.append("- None extracted yet.")
    lines.extend(["", "## Required Evidence Modes"])
    if spec.core_claims:
        for claim in spec.core_claims:
            evidence_mode = "proof" if "theory" in spec.contribution_type else "experiment"
            lines.append(f"- {claim.id}: {evidence_mode}")
    else:
        lines.append("- None inferred yet.")
    write_text(project_root / "01_spec/contribution_hypotheses.md", "\n".join(lines) + "\n")
    write_text(project_root / "01_spec/spec_agent_notes.md", _spec_agent_notes(spec))


def _parse_markdown_sections(text: str) -> tuple[str, dict[str, list[str]]]:
    title: str | None = None
    current_heading = "__root__"
    sections: dict[str, list[str]] = {current_heading: []}
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading_match = HEADING_RE.match(line)
        if heading_match:
            heading = heading_match.group("title").strip()
            if title is None:
                title = heading
            current_heading = heading.lower()
            sections.setdefault(current_heading, [])
            continue
        sections.setdefault(current_heading, []).append(line)
    return title or "", sections


def _extract_target_journal(path: Path, journal_family: str) -> str:
    if not path.exists():
        return journal_family
    for line in path.read_text(encoding="utf-8").splitlines():
        match = BULLET_RE.match(line)
        if match:
            return match.group("item").strip()
    return journal_family


def _extract_problem_statement(sections: dict[str, list[str]]) -> str:
    for keyword in ("problem", "summary", "overview", "motivation", "__root__"):
        for heading, lines in sections.items():
            if keyword == "__root__" and heading != "__root__":
                continue
            if keyword != "__root__" and keyword not in heading:
                continue
            paragraph = _first_paragraph_from_lines(lines)
            if paragraph:
                return paragraph
    return ""


def _extract_claims(sections: dict[str, list[str]]) -> list[ClaimRecord]:
    claim_lines: list[str] = []
    for heading, lines in sections.items():
        if any(keyword in heading for keyword in ("claim", "contribution", "result", "theorem", "hypothesis")):
            claim_lines.extend(_extract_bullets(lines))
    if not claim_lines:
        root_lines = sections.get("__root__", [])
        for line in root_lines:
            stripped = line.strip()
            if stripped.lower().startswith(("we show", "we prove", "we study", "we establish")):
                claim_lines.append(stripped)
    claims: list[ClaimRecord] = []
    for index, claim in enumerate(claim_lines, start=1):
        claims.append(ClaimRecord(id=f"C{index}", text=claim))
    return claims


def _extract_assumptions(sections: dict[str, list[str]]) -> list[str]:
    assumptions: list[str] = []
    for heading, lines in sections.items():
        if any(keyword in heading for keyword in ("assumption", "setting", "condition", "regime")):
            assumptions.extend(_extract_bullets(lines))
    return assumptions


def _extract_bullets(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    for line in lines:
        match = BULLET_RE.match(line)
        if match:
            bullets.append(match.group("item").strip())
    return bullets


def _first_paragraph_from_lines(lines: list[str]) -> str:
    chunks: list[str] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                chunks.append(" ".join(current))
                current = []
            continue
        if BULLET_RE.match(stripped):
            continue
        current.append(stripped)
    if current:
        chunks.append(" ".join(current))
    return chunks[0] if chunks else ""


def _first_non_heading_paragraph(text: str) -> str:
    sections = []
    current: list[str] = []
    for line in text.splitlines():
        if HEADING_RE.match(line):
            if current:
                sections.append(" ".join(current))
                current = []
            continue
        stripped = line.strip()
        if not stripped:
            if current:
                sections.append(" ".join(current))
                current = []
            continue
        if BULLET_RE.match(stripped):
            continue
        current.append(stripped)
    if current:
        sections.append(" ".join(current))
    return sections[0] if sections else ""


def _infer_contribution_types(text: str) -> list[str]:
    lowered = text.lower()
    contribution_types: list[str] = []
    if any(token in lowered for token in ("theorem", "lemma", "proof", "prove", "proposition", "corollary", "theory-led")):
        contribution_types.append("theory")
    if any(token in lowered for token in ("experiment", "synthetic", "dataset", "simulation", "empirical", "real data")):
        contribution_types.append("experiment")
    if not contribution_types:
        contribution_types.append("theory")
    return contribution_types


def _infer_dataset_needs(text: str) -> list[str]:
    lowered = text.lower()
    needs: list[str] = []
    if "synthetic" in lowered or "simulation" in lowered:
        needs.append("synthetic")
    if "public data" in lowered or "public dataset" in lowered:
        needs.append("public_real_data")
    elif "real data" in lowered or "dataset" in lowered:
        needs.append("real_data")
    return needs


def _humanize_project_name(project_name: str) -> str:
    return project_name.replace("-", " ").replace("_", " ").title()


def _refine_spec_with_provider(
    *,
    project_root: Path,
    spec: PaperSpec,
    idea_text: str,
    constraints_text: str,
    target_journal: str,
) -> PaperSpec:
    payload = complete_json_with_openai(
        project_root=project_root,
        prompt_path="agents/spec.md",
        prompt=(
            "Normalize this research idea into a paper spec JSON object.\n\n"
            f"Target journal: {target_journal}\n\n"
            "Idea markdown:\n"
            f"{idea_text}\n\n"
            "Constraints:\n"
            f"{constraints_text}"
        ),
        fallback={},
        max_output_tokens=1200,
    )
    if not payload:
        return spec

    claim_texts = [item for item in payload.get("core_claims", []) if isinstance(item, str) and item.strip()]
    assumptions = [item for item in payload.get("assumptions", []) if isinstance(item, str) and item.strip()]
    contribution_type = [
        item for item in payload.get("contribution_type", []) if item in {"theory", "experiment"}
    ] or spec.contribution_type
    dataset_needs = [
        item for item in payload.get("dataset_needs", []) if item in {"synthetic", "public_real_data", "real_data"}
    ] or spec.dataset_needs

    refined_claims = [
        ClaimRecord(id=f"C{index}", text=text)
        for index, text in enumerate(claim_texts, start=1)
    ] or spec.core_claims

    return PaperSpec(
        title_working=str(payload.get("title_working") or spec.title_working),
        problem_statement=str(payload.get("problem_statement") or spec.problem_statement),
        contribution_type=contribution_type,
        target_journal=spec.target_journal,
        journal_family=spec.journal_family,
        core_claims=refined_claims,
        assumptions=assumptions or spec.assumptions,
        dataset_needs=dataset_needs,
    )


def _spec_agent_notes(spec: PaperSpec) -> str:
    lines = [
        "# Spec Agent Notes",
        "",
        f"- Working title: `{spec.title_working or 'Untitled'}`",
        f"- Contribution types: `{', '.join(spec.contribution_type) or 'unspecified'}`",
        f"- Core claims: `{len(spec.core_claims)}`",
        f"- Assumptions: `{len(spec.assumptions)}`",
        f"- Dataset needs: `{', '.join(spec.dataset_needs) or 'none'}`",
    ]
    return "\n".join(lines) + "\n"
