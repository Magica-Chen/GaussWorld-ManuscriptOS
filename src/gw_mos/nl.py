from __future__ import annotations

import re
from pathlib import Path

from gw_mos.controller.engine import ControllerEngine
from gw_mos.controller.stages import Stage
from gw_mos.journals.discovery import resolve_template
from gw_mos.literature.pipeline import ingest_literature
from gw_mos.nl_types import RoutedPlan
from gw_mos.providers.planner import maybe_plan_with_providers
from pydantic import BaseModel


class ExecutionResult(BaseModel):
    project_path: Path | None
    output: str


def route_request(request: str, current_stage: Stage | None = None) -> RoutedPlan:
    text = request.strip()
    lowered = text.lower()
    plan = RoutedPlan()

    if not text:
        plan.explanation = "No request provided."
        return plan

    if _is_init_request(lowered):
        plan.init_project = True
        plan.project_name = _extract_project_name(text)
        plan.journal = _extract_journal_family(lowered)
        plan.show_status = True
        plan.explanation = "Create a project from a natural-language initialization request."
        return plan

    if _mentions_help(lowered):
        plan.explanation = "Show available natural-language workflow commands."
        return plan

    if _mentions_next(lowered) and current_stage is not None:
        next_stage = _next_stage_after(current_stage)
        if next_stage is not None:
            plan.stages = [next_stage]
            plan.show_status = True
            plan.explanation = f"Advance to the next stage after {current_stage.value}."
            return plan

    if any(token in lowered for token in ("submission ready", "full pipeline", "prepare the paper", "paper completion")):
        plan.stages = [
            Stage.spec,
            Stage.novelty,
            Stage.theory_program,
            Stage.proof_audit,
            Stage.journal_fit,
            Stage.experiment_design,
            Stage.scaffold_draft,
            Stage.experiment_run,
            Stage.alignment_review,
            Stage.final_write,
            Stage.build_qa,
        ]
        plan.show_status = True
        plan.show_qa = True
        plan.show_readiness = True
        plan.show_bundle = True
        plan.explanation = "Run the main theory-paper pipeline through build."
        return plan

    if any(token in lowered for token in ("submission bundle", "bundle the paper", "export submission", "package submission")):
        plan.stages.append(Stage.build_qa)
        plan.show_status = True
        plan.show_qa = True
        plan.show_readiness = True
        plan.show_bundle = True
        plan.explanation = "Build the current manuscript and surface the submission bundle."
        return plan

    if any(token in lowered for token in ("submission readiness", "ready for submission", "readiness report", "are we ready")):
        plan.show_status = True
        plan.show_readiness = True
        plan.explanation = "Show the submission-readiness verdict for the current project."
        return plan

    if any(token in lowered for token in ("build", "compile", "pdf", "latex")):
        if any(token in lowered for token in ("draft", "write", "scaffold")):
            plan.stages.extend([Stage.scaffold_draft, Stage.build_qa])
        else:
            plan.stages.append(Stage.build_qa)
        plan.show_qa = True
        plan.show_readiness = True
        plan.show_status = True
        plan.explanation = "Compile the manuscript and surface the QA report."
        return plan

    if any(token in lowered for token in ("draft", "write the paper", "write manuscript", "scaffold")):
        plan.stages.append(Stage.scaffold_draft)
        plan.show_status = True
        plan.explanation = "Generate or refresh the LaTeX draft scaffold."
        return plan

    if any(token in lowered for token in ("proof audit", "audit the proof", "counterexample", "stress test theory", "skeptical review")):
        plan.stages.append(Stage.proof_audit)
        plan.show_status = True
        plan.explanation = "Run the proof-audit artefacts."
        return plan

    if any(token in lowered for token in ("theory", "theorem", "assumption", "proof", "ledger", "notation")):
        plan.stages.append(Stage.theory_program)
        plan.show_status = True
        plan.explanation = "Generate the theory program artefacts."
        return plan

    if any(token in lowered for token in ("experiment", "validation", "synthetic study", "real data", "dataset plan")):
        plan.stages.append(Stage.experiment_design)
        plan.show_status = True
        plan.explanation = "Generate the experiment design artefacts."
        return plan

    if any(token in lowered for token in ("run experiments", "check experiment status", "results audit", "audit experiment")):
        plan.stages.append(Stage.experiment_run)
        plan.show_status = True
        plan.explanation = "Refresh experiment execution and audit artefacts."
        return plan

    if any(token in lowered for token in ("claim evidence", "alignment", "audit claims", "evidence matrix")):
        plan.stages.append(Stage.alignment_review)
        plan.show_status = True
        plan.explanation = "Refresh the claim-evidence audit artefacts."
        return plan

    if any(token in lowered for token in ("final write", "polish sections", "synthesize draft")):
        plan.stages.append(Stage.final_write)
        plan.show_status = True
        plan.explanation = "Rewrite the manuscript sections from current artefacts."
        return plan

    if any(token in lowered for token in ("search literature", "find papers", "search public references", "search references", "find related papers")):
        plan.search_public_literature = True
        plan.show_status = True
        plan.explanation = "Search public metadata sources and ingest grounded references."
        return plan

    if any(token in lowered for token in ("literature", "bib", "bibtex", "reference", "references", "paper pdf", "papers")):
        plan.ingest_literature = True
        if "search" in lowered or "find" in lowered or "public" in lowered:
            plan.search_public_literature = True
        if "novelty" in lowered or "review" in lowered:
            plan.stages.append(Stage.novelty)
        plan.show_status = True
        plan.explanation = "Ingest literature inputs and optionally refresh novelty artefacts."
        return plan

    if any(token in lowered for token in ("novelty", "related work")):
        plan.stages.append(Stage.novelty)
        plan.show_status = True
        plan.explanation = "Refresh the novelty map from local literature artefacts."
        return plan

    if any(token in lowered for token in ("journal", "template", "venue", "scope")):
        plan.stages.append(Stage.journal_fit)
        plan.show_journal = True
        plan.show_status = True
        plan.explanation = "Inspect or refresh journal/template fit."
        return plan

    if any(token in lowered for token in ("spec", "normalize", "understand idea", "summarize idea", "intake")):
        plan.stages.append(Stage.spec)
        plan.show_status = True
        plan.explanation = "Regenerate the normalized paper specification."
        return plan

    if any(token in lowered for token in ("status", "where are we", "progress", "check project")):
        plan.show_status = True
        plan.explanation = "Show current project status."
        return plan

    plan.show_status = True
    plan.explanation = "No strong intent match; default to showing project status."
    return plan


def execute_request(
    request: str,
    *,
    project_path: Path | None,
    root: Path,
    project_name: str | None = None,
    journal: str = "custom",
    template: Path | None = None,
    bib_paths: list[Path] | None = None,
    pdf_paths: list[Path] | None = None,
) -> ExecutionResult:
    engine = ControllerEngine()
    current_stage = None
    if project_path is not None and project_path.exists():
        current_stage = engine.get_state(project_path).current_stage

    plan = route_request(request, current_stage=current_stage)
    provider_plan = maybe_plan_with_providers(
        request_text=request,
        deterministic_plan=plan,
        current_stage=current_stage,
        project_path=project_path,
    )
    if provider_plan is not None:
        plan = provider_plan.plan
    lines = []

    if plan.init_project:
        resolved_name = project_name or plan.project_name
        if not resolved_name:
            raise ValueError("Could not infer a project name from the request. Pass --name.")
        resolved_journal = _journal_override(journal, plan.journal)
        project_path = engine.initialise_project(root=root, project_name=resolved_name, journal=resolved_journal, template=template)
        lines.append(f"Initialized project at {project_path}")

    if project_path is None:
        raise ValueError("This request requires a project path. Pass --project or initialize a project first.")

    if plan.ingest_literature:
        summary = ingest_literature(project_root=project_path, bib_paths=bib_paths or [], pdf_paths=pdf_paths or [])
        lines.extend(
            [
                "Literature ingest completed.",
                f"- grounded_entries={summary.grounded_entries}",
                f"- provisional_entries={summary.provisional_entries}",
                f"- notes_written={summary.notes_written}",
            ]
        )

    if plan.search_public_literature:
        search_summary = search_and_ingest_public_metadata(
            project_root=project_path,
            query=plan.literature_query,
        )
        lines.extend(
            [
                "Public literature search completed.",
                f"- query={search_summary.query}",
                f"- result_count={search_summary.result_count}",
                f"- grounded_entries={search_summary.grounded_entries}",
                f"- notes_written={search_summary.notes_written}",
            ]
        )

    for stage in plan.stages:
        state = engine.run_stage(project_path=project_path, stage=stage)
        lines.append(f"Ran stage `{stage.value}` -> `{state.stage_status}`")

    if plan.show_journal:
        state = engine.get_state(project_path)
        inspection = resolve_template(
            journal_family=state.journal_family,
            project_root=project_path,
            explicit_template=state.template_path,
        )
        lines.extend(
            [
                "Journal/template inspection:",
                f"- resolved_family={inspection.resolved_family}",
                f"- template={inspection.selected_path or 'not found'}",
                f"- main_tex={inspection.main_tex[0] if inspection.main_tex else 'none'}",
            ]
        )

    if plan.show_qa:
        report_path = project_path / "06_qa/qa_report.md"
        if report_path.exists():
            lines.extend(["", report_path.read_text(encoding="utf-8").strip()])

    if plan.show_readiness:
        readiness_path = project_path / "06_qa/submission_readiness.md"
        if readiness_path.exists():
            lines.extend(["", readiness_path.read_text(encoding="utf-8").strip()])
        else:
            lines.extend(["", "Submission readiness report not generated yet. Run `build the pdf` or `prepare the paper to be submission ready`."])

    if plan.show_bundle:
        bundle_manifest = project_path / "07_submission/manifest.md"
        if bundle_manifest.exists():
            lines.extend(["", bundle_manifest.read_text(encoding="utf-8").strip()])

    if plan.show_status or not lines:
        lines.extend(["", engine.render_status(project_path)])

    if plan.explanation:
        lines.insert(0, f"intent={plan.explanation}")
    if plan.source != "deterministic":
        lines.insert(0, f"planner={plan.source}")
    if plan.review_note:
        lines.append(f"review={plan.review_note}")
    if plan.assistant_reply:
        lines.append(plan.assistant_reply)

    return ExecutionResult(project_path=project_path, output="\n".join(line for line in lines if line is not None).strip() + "\n")


def help_text() -> str:
    return (
        "Natural-language examples:\n"
        "- create a new project called social-proof for elsevier\n"
        "- run spec on this project\n"
        "- ingest literature from these bib files and refresh novelty\n"
        "- build the pdf\n"
        "- design the experiments\n"
        "- run a proof audit\n"
        "- audit experiment results\n"
        "- refresh the claim evidence matrix\n"
        "- synthesize the draft sections\n"
        "- prepare the draft\n"
        "- go to next\n"
        "- check status\n"
    )


def _is_init_request(lowered: str) -> bool:
    return any(phrase in lowered for phrase in ("create project", "new project", "init project", "start a project"))


def _mentions_help(lowered: str) -> bool:
    return lowered in {"help", "?"} or "what can you do" in lowered or "examples" in lowered


def _mentions_next(lowered: str) -> bool:
    return lowered in {"next", "go next", "go to next"} or "next step" in lowered


def _extract_project_name(text: str) -> str | None:
    quoted = re.search(r'["\']([A-Za-z0-9._-]+)["\']', text)
    if quoted:
        return quoted.group(1)
    named = re.search(r"(?:called|named)\s+([A-Za-z0-9._-]+)", text, re.IGNORECASE)
    if named:
        return named.group(1)
    project = re.search(r"project\s+([A-Za-z0-9._-]+)", text, re.IGNORECASE)
    if project:
        return project.group(1)
    return None


def _extract_journal_family(lowered: str) -> str:
    if "elsevier" in lowered:
        return "elsevier"
    if "springer" in lowered or "nature" in lowered:
        return "springer_nature"
    return "custom"


def _next_stage_after(current_stage: Stage) -> Stage | None:
    ordered = Stage.ordered()
    try:
        index = ordered.index(current_stage)
    except ValueError:
        return None
    if index + 1 >= len(ordered):
        return current_stage
    return ordered[index + 1]


def _journal_override(cli_journal: str, inferred_journal: str) -> str:
    return cli_journal if cli_journal != "custom" else inferred_journal
