from __future__ import annotations

import csv
from pathlib import Path

import yaml

from gw_mos.agent_runtime import complete_with_openai
from gw_mos.artifacts.models import PaperSpec
from gw_mos.artifacts.readers import read_json, read_text
from gw_mos.artifacts.writers import write_text


def synthesis_pass(project_root: Path) -> dict[str, str]:
    spec = _load_spec(project_root)
    novelty_map = _safe_read(project_root / "02_literature/novelty_map.md")
    theorem_ledger = _safe_read(project_root / "03_theory/theorem_ledger.md")
    assumptions = _safe_read(project_root / "03_theory/assumptions.md")
    experiment_plan = _safe_read(project_root / "04_experiments/experiment_plan.md")
    alignment_rows = _load_claim_matrix(project_root)
    results = read_json(project_root / "04_experiments/results_registry.json")

    section_root = project_root / "05_draft/sections"
    section_root.mkdir(parents=True, exist_ok=True)

    write_text(
        section_root / "introduction.tex",
        _render_with_agent(
            project_root=project_root,
            section_name="Introduction",
            fallback=_render_introduction(spec, alignment_rows),
            context=_writer_context(spec, novelty_map, theorem_ledger, experiment_plan, alignment_rows, results),
        ),
    )
    write_text(
        section_root / "related_work.tex",
        _render_with_agent(
            project_root=project_root,
            section_name="Related Work",
            fallback=_render_related_work(novelty_map),
            context=_writer_context(spec, novelty_map, theorem_ledger, experiment_plan, alignment_rows, results),
        ),
    )
    write_text(
        section_root / "theory.tex",
        _render_with_agent(
            project_root=project_root,
            section_name="Theoretical Results",
            fallback=_render_theory(spec, theorem_ledger, assumptions),
            context=_writer_context(spec, novelty_map, theorem_ledger, experiment_plan, alignment_rows, results),
        ),
    )
    if "experiment" in spec.contribution_type or (section_root / "experiments.tex").exists():
        write_text(
            section_root / "experiments.tex",
            _render_with_agent(
                project_root=project_root,
                section_name="Experiments",
                fallback=_render_experiments(spec, experiment_plan, results),
                context=_writer_context(spec, novelty_map, theorem_ledger, experiment_plan, alignment_rows, results),
            ),
        )
    write_text(
        section_root / "discussion.tex",
        _render_with_agent(
            project_root=project_root,
            section_name="Discussion",
            fallback=_render_discussion(alignment_rows),
            context=_writer_context(spec, novelty_map, theorem_ledger, experiment_plan, alignment_rows, results),
        ),
    )
    write_text(
        section_root / "conclusion.tex",
        _render_with_agent(
            project_root=project_root,
            section_name="Conclusion",
            fallback=_render_conclusion(spec, alignment_rows),
            context=_writer_context(spec, novelty_map, theorem_ledger, experiment_plan, alignment_rows, results),
        ),
    )
    return {
        "status": "completed",
        "sections_root": str(section_root),
    }


def _render_introduction(spec: PaperSpec, alignment_rows: list[dict[str, str]]) -> str:
    contribution_lines = [f"\\item {claim.text}" for claim in spec.core_claims] or ["\\item Main contribution to be refined."]
    evidence_line = _alignment_summary(alignment_rows)
    body = "\n".join(
        [
            "\\section{Introduction}",
            "\\label{sec:introduction}",
            "",
            spec.problem_statement or "This manuscript develops the main research problem described by the user.",
            "",
            "The current draft is organized around the following core contributions:",
            "\\begin{itemize}",
            *contribution_lines,
            "\\end{itemize}",
            "",
            evidence_line,
            "",
            "This introduction should be revised once proofs, experiments, and venue-specific framing stabilize.",
        ]
    )
    return body + "\n"


def _render_related_work(novelty_map: str) -> str:
    excerpt = _first_nonempty_lines(novelty_map, limit=8)
    body = [
        "\\section{Related Work}",
        "\\label{sec:related-work}",
        "",
        "The current related-work section is grounded in the local novelty map.",
        "",
    ]
    if excerpt:
        body.append("\\begin{itemize}")
        body.extend(f"\\item {_escape_tex(line)}" for line in excerpt)
        body.append("\\end{itemize}")
    else:
        body.append("No grounded literature summary is available yet.")
    body.append("This section should be tightened after a fuller literature pass.")
    return "\n".join(body) + "\n"


def _render_theory(spec: PaperSpec, theorem_ledger: str, assumptions: str) -> str:
    ledger_lines = _first_nonempty_lines(theorem_ledger, limit=10)
    assumption_lines = _first_nonempty_lines(assumptions, limit=6)
    body = [
        "\\section{Theoretical Results}",
        "\\label{sec:theory}",
        "",
        "This section summarizes the current theorem program and should later be replaced by formal statements and proofs.",
        "",
    ]
    if spec.assumptions:
        body.append("Current extracted assumptions include:")
        body.append("\\begin{itemize}")
        body.extend(f"\\item {_escape_tex(item)}" for item in spec.assumptions)
        body.append("\\end{itemize}")
        body.append("")
    if ledger_lines:
        body.append("Current theorem ledger highlights:")
        body.append("\\begin{itemize}")
        body.extend(f"\\item {_escape_tex(line)}" for line in ledger_lines)
        body.append("\\end{itemize}")
        body.append("")
    if assumption_lines:
        body.append("Assumption coverage notes:")
        body.append("\\begin{itemize}")
        body.extend(f"\\item {_escape_tex(line)}" for line in assumption_lines)
        body.append("\\end{itemize}")
    return "\n".join(body) + "\n"


def _render_experiments(spec: PaperSpec, experiment_plan: str, results_registry: dict) -> str:
    plan_lines = _first_nonempty_lines(experiment_plan, limit=12)
    runs = results_registry.get("runs", [])
    body = [
        "\\section{Experiments}",
        "\\label{sec:experiments}",
        "",
        "The current experiment section summarizes the planned validation program.",
        "",
    ]
    if plan_lines:
        body.append("\\begin{itemize}")
        body.extend(f"\\item {_escape_tex(line)}" for line in plan_lines)
        body.append("\\end{itemize}")
    if runs:
        body.extend(
            [
                "",
                f"At this stage the results registry contains {len(runs)} planned or executed runs.",
                "Reported statuses remain provisional until the tmux experiment runner and result auditor complete the execution loop.",
            ]
        )
    if spec.dataset_needs:
        body.extend(
            [
                "",
                "Dataset requirements currently inferred for this project are:",
                "\\begin{itemize}",
                *(f"\\item {_escape_tex(item)}" for item in spec.dataset_needs),
                "\\end{itemize}",
            ]
        )
    return "\n".join(body) + "\n"


def _render_discussion(alignment_rows: list[dict[str, str]]) -> str:
    unresolved = [row for row in alignment_rows if row.get("status") != "pass"]
    body = [
        "\\section{Discussion}",
        "\\label{sec:discussion}",
        "",
        "The manuscript remains under active development and should be interpreted as a structured draft rather than a finished submission.",
        "",
    ]
    if unresolved:
        body.extend(
            [
                "The main unresolved evidence gaps are:",
                "\\begin{itemize}",
                *(f"\\item Claim {row['claim_id']} is currently marked as {_escape_tex(row['status'])}." for row in unresolved[:8]),
                "\\end{itemize}",
            ]
        )
    else:
        body.append("All tracked claims currently have passing evidence tags in the local claim-evidence matrix.")
    body.append("Future revisions should reconcile any remaining gaps before journal-style polishing.")
    return "\n".join(body) + "\n"


def _render_conclusion(spec: PaperSpec, alignment_rows: list[dict[str, str]]) -> str:
    passing = sum(1 for row in alignment_rows if row.get("status") == "pass")
    total = len(alignment_rows)
    return (
        "\\section{Conclusion}\n"
        "\\label{sec:conclusion}\n\n"
        f"This draft currently centers on {_escape_tex(spec.title_working or 'the working manuscript')} and tracks {total} major claims, of which {passing} currently have passing evidence tags in the local audit. "
        "The final conclusion should be revisited after proofs are completed and experiments are run.\n"
    )


def _load_spec(project_root: Path) -> PaperSpec:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    return PaperSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))


def _safe_read(path: Path) -> str:
    if not path.exists():
        return ""
    return read_text(path)


def _load_claim_matrix(project_root: Path) -> list[dict[str, str]]:
    path = project_root / "06_qa/claim_evidence_matrix.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _alignment_summary(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "The current draft has not yet run a claim-evidence audit."
    passing = sum(1 for row in rows if row.get("status") == "pass")
    return f"The current claim-evidence audit marks {passing} of {len(rows)} tracked claims as passing."


def _first_nonempty_lines(text: str, limit: int) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped.lstrip("- ").strip())
        if len(lines) >= limit:
            break
    return lines


def _escape_tex(value: str) -> str:
    replacements = {
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
    }
    escaped = value
    for source, target in replacements.items():
        escaped = escaped.replace(source, target)
    return escaped


def _writer_context(
    spec: PaperSpec,
    novelty_map: str,
    theorem_ledger: str,
    experiment_plan: str,
    alignment_rows: list[dict[str, str]],
    results: dict,
) -> str:
    claim_rows = "\n".join(
        f"- {row.get('claim_id')}: {row.get('classification')} / {row.get('status')}"
        for row in alignment_rows[:12]
    )
    return "\n".join(
        [
            f"Working title: {spec.title_working}",
            f"Problem statement: {spec.problem_statement}",
            "Core claims:",
            *[f"- {claim.id}: {claim.text}" for claim in spec.core_claims],
            "",
            "Novelty excerpt:",
            *_first_nonempty_lines(novelty_map, limit=10),
            "",
            "Theory excerpt:",
            *_first_nonempty_lines(theorem_ledger, limit=12),
            "",
            "Experiment excerpt:",
            *_first_nonempty_lines(experiment_plan, limit=12),
            "",
            "Claim evidence:",
            claim_rows,
            "",
            f"Registered runs: {len(results.get('runs', []))}",
        ]
    )


def _render_with_agent(*, project_root: Path, section_name: str, fallback: str, context: str) -> str:
    generated = complete_with_openai(
        project_root=project_root,
        prompt_path="agents/writer.md",
        prompt=(
            f"Write the LaTeX for the `{section_name}` section.\n"
            "Return only LaTeX section content including the \\section{...} heading.\n\n"
            f"{context}"
        ),
        fallback=fallback,
        max_output_tokens=1800,
    )
    if "\\section{" not in generated:
        return fallback
    return generated.strip() + "\n"
