from __future__ import annotations

from pathlib import Path

import yaml

from gw_mos.artifacts.models import PaperSpec, ProjectState, RuntimeStatus
from gw_mos.artifacts.paths import ensure_project_directories
from gw_mos.controller.stages import Stage
from gw_mos.utils.json_io import save_json


def create_project_workspace(project_root: Path, journal: str, template: Path | None = None) -> None:
    ensure_project_directories(project_root)

    starter_files: dict[str, str] = {
        "00_intake/idea.md": "# Research Idea\n\nDescribe the problem, claims, assumptions, and intended venue.\n",
        "00_intake/constraints.md": "# Constraints\n\nList user constraints and non-negotiables.\n",
        "00_intake/journal_targets.md": f"# Journal Targets\n\n- {journal}\n",
        "01_spec/contribution_hypotheses.md": "# Contribution Hypotheses\n\n",
        "01_spec/journal_fit.md": "# Journal Fit\n\n",
        "02_literature/novelty_map.md": "# Novelty Map\n\n",
        "02_literature/library.bib": "% Grounded citations only.\n",
        "02_literature/citation_index.json": "{\n  \"papers\": []\n}\n",
        "03_theory/theorem_ledger.md": "# Theorem Ledger\n\n",
        "03_theory/assumptions.md": "# Assumptions\n\n",
        "03_theory/notation.md": "# Notation\n\n",
        "03_theory/counterexamples.md": "# Counterexamples\n\n",
        "03_theory/proof_audit.md": "# Proof Audit\n\n",
        "04_experiments/experiment_plan.md": "# Experiment Plan\n\n",
        "04_experiments/results_registry.json": "{\n  \"runs\": []\n}\n",
        "04_experiments/results_audit.md": "# Results Audit\n\n",
        "05_draft/main.tex": _starter_main_tex(),
        "06_qa/claim_evidence_matrix.csv": "claim_id,claim_text,classification,evidence_type,evidence_ref,status\n",
        "06_qa/qa_report.md": "# QA Report\n\n",
        "06_qa/submission_readiness.md": "# Submission Readiness\n\n",
        "06_qa/compile_log.txt": "",
        "07_submission/manifest.md": "# Submission Bundle\n\n",
    }

    for relative_path, content in starter_files.items():
        file_path = project_root / relative_path
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")

    spec = PaperSpec(journal_family=journal, target_journal=journal)
    spec_path = project_root / "01_spec/paper_spec.yaml"
    if not spec_path.exists():
        spec_path.write_text(yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False), encoding="utf-8")

    state = ProjectState(
        project_name=project_root.name,
        journal_family=journal,
        template_path=str(template) if template else None,
        current_stage=Stage.intake,
        stage_status="ready",
    )
    status = RuntimeStatus(
        project=project_root.name,
        current_stage=Stage.intake,
        stage_status="ready",
        active_agent="controller",
        submission_ready="unknown",
    )
    if not (project_root / "runtime/state.json").exists():
        save_json(project_root / "runtime/state.json", state.model_dump(mode="json"))
    if not (project_root / "runtime/status.json").exists():
        save_json(project_root / "runtime/status.json", status.model_dump(mode="json"))
    if not (project_root / "runtime/tmux_jobs.json").exists():
        save_json(project_root / "runtime/tmux_jobs.json", {"jobs": []})


def _starter_main_tex() -> str:
    return (
        "\\documentclass{article}\n"
        "\\title{Working Title}\n"
        "\\author{Author}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        "\\section{Introduction}\n"
        "Scaffold draft.\n"
        "\\end{document}\n"
    )
