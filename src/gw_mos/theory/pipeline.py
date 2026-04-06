from __future__ import annotations

from pathlib import Path

import yaml

from gw_mos.agent_runtime import complete_with_openai
from gw_mos.artifacts.models import PaperSpec
from gw_mos.artifacts.writers import write_text
from gw_mos.theory.assumptions import missing_assumption_topics, normalized_assumptions
from gw_mos.theory.counterexamples import counterexample_prompts
from gw_mos.theory.notation import notation_report
from gw_mos.theory.theorem_ledger import LedgerEntry, build_theorem_ledger


def generate_theory_program(project_root: Path) -> None:
    spec = _load_spec(project_root)
    assumptions = normalized_assumptions(spec)
    missing_topics = missing_assumption_topics(spec)
    notation = notation_report(spec)
    ledger = build_theorem_ledger(spec)
    agent_notes = complete_with_openai(
        project_root=project_root,
        prompt_path="agents/theory_architect.md",
        prompt=(
            f"Working title: {spec.title_working}\n"
            f"Problem statement: {spec.problem_statement}\n"
            + "\n".join(f"- {claim.id}: {claim.text}" for claim in spec.core_claims)
        ),
        fallback="",
        max_output_tokens=600,
    )

    write_text(project_root / "03_theory/theorem_ledger.md", render_theorem_ledger(spec, ledger["entries"], ledger["dependencies"], agent_notes))
    write_text(project_root / "03_theory/assumptions.md", render_assumptions(spec, assumptions, missing_topics))
    write_text(project_root / "03_theory/notation.md", render_notation(spec, notation))
    write_text(project_root / "03_theory/counterexamples.md", render_counterexamples(spec, ledger["entries"], missing_topics))


def render_theorem_ledger(spec: PaperSpec, entries: list[LedgerEntry], dependencies: list[str], agent_notes: str = "") -> str:
    lines = [
        "# Theorem Ledger",
        "",
        f"- Working title: `{spec.title_working or 'Untitled'}`",
        f"- Problem statement: {spec.problem_statement or 'Not yet specified.'}",
        f"- Contribution modes: `{', '.join(spec.contribution_type) or 'unspecified'}`",
        "",
        "## Dependency Backbone",
    ]
    if dependencies:
        lines.extend(f"- {dependency}" for dependency in dependencies)
    else:
        lines.append("- No explicit dependency backbone inferred yet.")

    lines.extend(["", "## Ledger Entries"])
    for entry in entries:
        lines.extend(
            [
                f"### {entry.label}",
                f"- Claim ID: `{entry.claim_id}`",
                f"- Kind: `{entry.kind}`",
                f"- Statement: {entry.statement}",
                f"- Proof status: `{entry.proof_status}`",
                f"- Evidence mode: `{entry.evidence_mode}`",
                f"- Dependencies: {', '.join(entry.dependencies) if entry.dependencies else 'none'}",
                f"- Empirical implication: {_empirical_implication(entry)}",
                "",
            ]
        )
    if agent_notes:
        lines.extend(["## Agent Notes", agent_notes.strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def render_assumptions(spec: PaperSpec, assumptions: list[str], missing_topics: list[str]) -> str:
    lines = [
        "# Assumptions",
        "",
        "## Declared Assumptions",
    ]
    if assumptions:
        lines.extend(f"- A{index}: {assumption}" for index, assumption in enumerate(assumptions, start=1))
    else:
        lines.append("- None extracted from the current spec.")

    lines.extend(["", "## Coverage Checklist"])
    if missing_topics:
        lines.extend(f"- Missing explicit treatment of `{topic}`." for topic in missing_topics)
    else:
        lines.append("- Current assumptions touch the standard coverage checklist heuristically.")

    if "experiment" in spec.contribution_type:
        lines.extend(["", "## Experiment Alignment", "- Check whether the synthetic regime actually satisfies the same assumptions used by the main theorem."])
    return "\n".join(lines) + "\n"


def render_notation(spec: PaperSpec, notation: dict[str, list[str]]) -> str:
    lines = [
        "# Notation",
        "",
        "## Candidate Symbols",
    ]
    if notation["candidate_symbols"]:
        lines.extend(f"- `{symbol}`" for symbol in notation["candidate_symbols"])
    else:
        lines.append("- No candidate symbols inferred yet.")

    lines.extend(["", "## Diagnostics"])
    if notation["notes"]:
        lines.extend(f"- {note}" for note in notation["notes"])
    if notation["undefined_symbols"]:
        lines.extend(f"- {note}" for note in notation["undefined_symbols"])
    if not notation["notes"] and not notation["undefined_symbols"]:
        lines.append("- No notation diagnostics yet.")

    lines.extend(
        [
            "",
            "## Next Actions",
            "- Replace heuristic symbol guesses with formal notation before proof writing.",
            "- Align notation with the theorem ledger and experiment plan.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_counterexamples(spec: PaperSpec, entries: list[LedgerEntry], missing_topics: list[str]) -> str:
    lines = [
        "# Counterexamples",
        "",
        "## Prompts",
    ]
    lines.extend(f"- {prompt}" for prompt in counterexample_prompts())
    if missing_topics:
        lines.extend(f"- What fails if `{topic}` is weakened or omitted?" for topic in missing_topics)
    theorem_labels = [entry.label for entry in entries if entry.kind == "theorem"]
    if theorem_labels:
        lines.extend(f"- Try constructing a boundary-regime counterexample for {label}." for label in theorem_labels)
    lines.extend(
        [
            "",
            "## Notes",
            "- This file is a scaffold for later proof-auditor and adversarial-review stages.",
            f"- Contribution modes currently inferred: `{', '.join(spec.contribution_type) or 'unspecified'}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def _load_spec(project_root: Path) -> PaperSpec:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    return PaperSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))


def _empirical_implication(entry: LedgerEntry) -> str:
    if entry.kind == "theorem":
        return "Design a synthetic regime where the theorem's qualitative prediction can fail or hold sharply."
    if entry.kind == "empirical":
        return "Tie the validation protocol directly to the theorem regime and claimed scaling law."
    return "Clarify whether this claim should become a theorem, a lemma, or an experiment-specific observation."
