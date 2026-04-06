from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path

from gw_mos.qa.claims import claim_audit_summary
from gw_mos.qa.compile import CompileResult
from gw_mos.utils.json_io import load_json


@dataclass(frozen=True)
class SubmissionReadiness:
    verdict: str
    blockers: list[str]
    advisories: list[str]
    bundle_path: str


def render_qa_report(result: CompileResult, project_root: Path | None = None) -> str:
    status = "passed" if result.success else "failed"
    lines = [
        "# QA Report",
        "",
        "## Build",
        f"- Status: `{status}`",
        f"- Engine: `{result.engine}`",
        f"- Main file: `{result.main_tex}`",
        f"- PDF: `{result.pdf_path or 'not produced'}`",
        f"- Log: `{result.log_path}`",
        f"- Ran at: `{result.ran_at}`",
    ]
    if result.commands:
        lines.extend(["", "## Commands"])
        lines.extend(f"- `{' '.join(command.command)}` -> `{command.returncode}`" for command in result.commands)
    if result.missing_tools:
        lines.extend(["", "## Missing Tools"])
        lines.extend(f"- `{tool}`" for tool in result.missing_tools)
    if result.errors:
        lines.extend(["", "## Errors"])
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in result.warnings)
    if project_root is not None:
        lines.extend(_proof_audit_section(project_root))
        lines.extend(_experiment_audit_section(project_root))
        lines.extend(_claim_evidence_section(project_root))
        readiness = assess_submission_readiness(project_root=project_root, compile_result=result)
        lines.extend(
            [
                "",
                "## Submission Readiness",
                f"- Verdict: `{readiness.verdict}`",
                f"- Bundle: `{readiness.bundle_path}`",
            ]
        )
        if readiness.blockers:
            lines.extend(f"- Blocker: {blocker}" for blocker in readiness.blockers)
        if readiness.advisories:
            lines.extend(f"- Advisory: {advisory}" for advisory in readiness.advisories)
    if not result.errors and not result.warnings:
        lines.extend(["", "## Diagnostics", "- No extracted warnings or errors."])
    return "\n".join(lines) + "\n"


def write_qa_report(path: Path, result: CompileResult, project_root: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_qa_report(result, project_root=project_root), encoding="utf-8")


def assess_submission_readiness(project_root: Path, compile_result: CompileResult | None = None) -> SubmissionReadiness:
    blockers: list[str] = []
    advisories: list[str] = []
    bundle_root = project_root / "07_submission"

    build_success = compile_result.success if compile_result is not None else _latest_build_passed(project_root)
    if not build_success:
        blockers.append("The manuscript does not compile successfully yet.")

    proof_counts = _proof_audit_counts(project_root)
    if proof_counts["high"] > 0:
        blockers.append(f"The proof audit still has {proof_counts['high']} high-severity findings.")
    elif proof_counts["medium"] > 0:
        advisories.append(f"The proof audit still has {proof_counts['medium']} medium-severity findings.")

    experiment_statuses = _experiment_status_counts(project_root)
    if experiment_statuses:
        incomplete_statuses = {
            status: count
            for status, count in experiment_statuses.items()
            if status not in {"completed", "passed"}
        }
        if incomplete_statuses:
            details = ", ".join(f"{status}={count}" for status, count in sorted(incomplete_statuses.items()))
            blockers.append(f"Experiment execution is incomplete or failed ({details}).")
    elif _paper_expects_experiments(project_root):
        blockers.append("The paper expects experiments, but no experiment runs are registered.")

    claim_summary = claim_audit_summary(project_root)
    if claim_summary["missing"] > 0:
        blockers.append(f"The claim-evidence matrix still has {claim_summary['missing']} non-passing claims.")

    grounded_refs = _grounded_reference_count(project_root)
    if grounded_refs == 0:
        advisories.append("No grounded references are currently recorded in the citation index.")
    elif grounded_refs < 3:
        advisories.append(f"The grounded literature base is still thin ({grounded_refs} references).")

    verdict = "ready" if not blockers else "not_ready"
    return SubmissionReadiness(
        verdict=verdict,
        blockers=blockers,
        advisories=advisories,
        bundle_path=str(bundle_root),
    )


def write_submission_readiness(path: Path, project_root: Path, compile_result: CompileResult | None = None) -> SubmissionReadiness:
    readiness = assess_submission_readiness(project_root=project_root, compile_result=compile_result)
    lines = [
        "# Submission Readiness",
        "",
        f"- Verdict: `{readiness.verdict}`",
        f"- Bundle path: `{readiness.bundle_path}`",
        "",
        "## Blockers",
    ]
    if readiness.blockers:
        lines.extend(f"- {blocker}" for blocker in readiness.blockers)
    else:
        lines.append("- None.")
    lines.extend(["", "## Advisories"])
    if readiness.advisories:
        lines.extend(f"- {advisory}" for advisory in readiness.advisories)
    else:
        lines.append("- None.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return readiness


def build_submission_bundle(project_root: Path, compile_result: CompileResult | None = None) -> Path:
    bundle_root = project_root / "07_submission"
    source_root = bundle_root / "source"
    pdf_root = bundle_root / "pdf"
    report_root = bundle_root / "reports"

    for path in (source_root, pdf_root, report_root):
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    _copy_tree(project_root / "05_draft", source_root)
    library = project_root / "02_literature/library.bib"
    if library.exists():
        shutil.copy2(library, source_root / "library.bib")

    for report_name in ("qa_report.md", "submission_readiness.md", "compile_log.txt"):
        source = project_root / "06_qa" / report_name
        if source.exists():
            shutil.copy2(source, report_root / report_name)

    pdf_path = Path(compile_result.pdf_path) if compile_result and compile_result.pdf_path else project_root / "05_draft/main.pdf"
    if pdf_path.exists():
        shutil.copy2(pdf_path, pdf_root / pdf_path.name)

    manifest = [
        "# Submission Bundle",
        "",
        f"- Project: `{project_root.name}`",
        f"- Source directory: `{source_root}`",
        f"- PDF directory: `{pdf_root}`",
        f"- Reports directory: `{report_root}`",
        "",
        "## Included Files",
    ]
    for root in (source_root, pdf_root, report_root):
        files = sorted(path.relative_to(bundle_root).as_posix() for path in root.rglob("*") if path.is_file())
        if not files:
            manifest.append(f"- `{root.relative_to(bundle_root).as_posix()}`: none")
            continue
        manifest.append(f"- `{root.relative_to(bundle_root).as_posix()}`")
        manifest.extend(f"  - `{entry}`" for entry in files)
    (bundle_root / "manifest.md").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    return bundle_root


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if _should_skip_submission_file(path):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _should_skip_submission_file(path: Path) -> bool:
    name = path.name
    skipped_suffixes = {
        ".aux",
        ".bbl",
        ".bcf",
        ".blg",
        ".fdb_latexmk",
        ".fls",
        ".log",
        ".out",
        ".run.xml",
        ".synctex.gz",
        ".toc",
        ".pdf",
        ".qmd",
    }
    return any(name.endswith(suffix) for suffix in skipped_suffixes)


def _proof_audit_section(project_root: Path) -> list[str]:
    path = project_root / "03_theory/proof_audit.md"
    if not path.exists():
        return []
    counts = _proof_audit_counts(project_root)
    return [
        "",
        "## Proof Audit",
        f"- High-severity findings: `{counts['high']}`",
        f"- Medium-severity findings: `{counts['medium']}`",
        f"- Low-severity findings: `{counts['low']}`",
        f"- Source: `{path}`",
    ]


def _proof_audit_counts(project_root: Path) -> dict[str, int]:
    path = project_root / "03_theory/proof_audit.md"
    if not path.exists():
        return {"high": 0, "medium": 0, "low": 0}
    text = path.read_text(encoding="utf-8")
    return {
        "high": text.count("### HIGH:"),
        "medium": text.count("### MEDIUM:"),
        "low": text.count("### LOW:"),
    }


def _experiment_audit_section(project_root: Path) -> list[str]:
    path = project_root / "04_experiments/results_audit.md"
    if not path.exists():
        return []
    status_counts = _experiment_status_counts(project_root)
    lines = ["", "## Experiment Audit"]
    if status_counts:
        lines.extend(f"- `{status}`: `{count}`" for status, count in sorted(status_counts.items()))
    lines.append(f"- Source: `{path}`")
    return lines


def _experiment_status_counts(project_root: Path) -> dict[str, int]:
    registry = load_json(project_root / "04_experiments/results_registry.json")
    status_counts: dict[str, int] = {}
    for run in registry.get("runs", []):
        status = str(run.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
    return status_counts


def _claim_evidence_section(project_root: Path) -> list[str]:
    path = project_root / "06_qa/claim_evidence_matrix.csv"
    if not path.exists():
        return []
    summary = claim_audit_summary(project_root)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        "",
        "## Claim-Evidence Audit",
        f"- Passing claims: `{summary['pass']}`",
        f"- Non-passing claims: `{summary['missing']}`",
        f"- Total tracked claims: `{len(rows)}`",
        f"- Source: `{path}`",
    ]


def _latest_build_passed(project_root: Path) -> bool:
    report = project_root / "06_qa/qa_report.md"
    if not report.exists():
        return False
    return "Status: `passed`" in report.read_text(encoding="utf-8")


def _paper_expects_experiments(project_root: Path) -> bool:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    if not spec_path.exists():
        return False
    text = spec_path.read_text(encoding="utf-8")
    return "experiment" in text


def _grounded_reference_count(project_root: Path) -> int:
    payload = load_json(project_root / "02_literature/citation_index.json")
    return sum(1 for item in payload.get("papers", []) if item.get("verified"))
