from __future__ import annotations

from pathlib import Path

from gw_mos.artifacts.models import JobStatus, ProjectState, RuntimeStatus
from gw_mos.artifacts.writers import write_text
from gw_mos.artifacts.workspace import create_project_workspace
from gw_mos.controller.stages import Stage
from gw_mos.controller.state_store import StateStore
from gw_mos.experiments.audit import write_results_audit
from gw_mos.experiments.planner import generate_experiment_plan
from gw_mos.experiments.runner_tmux import TmuxRunner
from gw_mos.journals.discovery import render_inspection_markdown, resolve_template
from gw_mos.literature.pipeline import refresh_novelty_map
from gw_mos.qa.claims import write_claim_evidence_matrix
from gw_mos.qa.compile import compile_project
from gw_mos.qa.report import build_submission_bundle, write_qa_report, write_submission_readiness
from gw_mos.specification import build_paper_spec, write_spec_outputs
from gw_mos.theory.audit import generate_proof_audit
from gw_mos.theory.pipeline import generate_theory_program
from gw_mos.writing.scaffold import create_draft_scaffold
from gw_mos.writing.synthesis import synthesis_pass


class ControllerEngine:
    def __init__(self, state_store: StateStore | None = None) -> None:
        self.state_store = state_store or StateStore()

    def initialise_project(
        self,
        root: Path,
        project_name: str,
        journal: str,
        template: Path | None = None,
    ) -> Path:
        project_root = root / project_name
        create_project_workspace(project_root=project_root, journal=journal, template=template)
        return project_root

    def get_state(self, project_path: Path) -> ProjectState:
        return self.state_store.load_state(project_path)

    def get_status(self, project_path: Path) -> RuntimeStatus:
        return self.state_store.load_status(project_path)

    def run_stage(self, project_path: Path, stage: Stage) -> ProjectState:
        state = self.get_state(project_path)
        status = self.get_status(project_path)
        stage_status = self._execute_stage(project_path=project_path, stage=stage, state=state, status=status)
        state.current_stage = stage
        state.completed_stages = list(dict.fromkeys([*state.completed_stages, stage]))
        state.stage_status = stage_status
        status.current_stage = stage
        status.stage_status = stage_status
        status.active_agent = self._default_agent_for_stage(stage)
        self.state_store.save_state(project_path, state)
        self.state_store.save_status(project_path, status)
        return state

    def render_status(self, project_path: Path) -> str:
        state = self.get_state(project_path)
        status = self.get_status(project_path)
        blockers = ", ".join(status.blockers) if status.blockers else "none"
        return (
            f"project={state.project_name}\n"
            f"stage={state.current_stage.value}\n"
            f"stage_status={state.stage_status}\n"
            f"journal={state.journal_family}\n"
            f"template={state.template_path or 'auto-detect'}\n"
            f"active_agent={status.active_agent}\n"
            f"last_build={status.last_build.get('status', 'none')}\n"
            f"submission_ready={status.submission_ready}\n"
            f"blockers={blockers}"
        )

    def _default_agent_for_stage(self, stage: Stage) -> str:
        mapping = {
            Stage.intake: "spec_agent",
            Stage.spec: "spec_agent",
            Stage.novelty: "literature_agent",
            Stage.journal_fit: "journal_fit_agent",
            Stage.theory_program: "theory_architect_agent",
            Stage.proof_audit: "proof_auditor_agent",
            Stage.experiment_design: "experiment_designer_agent",
            Stage.scaffold_draft: "writing_agent",
            Stage.experiment_run: "results_auditor_agent",
            Stage.alignment_review: "claim_evidence_agent",
            Stage.final_write: "writing_agent",
            Stage.build_qa: "build_agent",
        }
        return mapping[stage]

    def _execute_stage(
        self,
        project_path: Path,
        stage: Stage,
        state: ProjectState,
        status: RuntimeStatus,
    ) -> str:
        if stage == Stage.intake:
            idea_path = project_path / "00_intake/idea.md"
            if not idea_path.exists():
                raise FileNotFoundError(f"Missing intake file: {idea_path}")
            return "completed"
        if stage == Stage.spec:
            spec = build_paper_spec(
                project_root=project_path,
                journal_family=state.journal_family,
                project_name=state.project_name,
            )
            write_spec_outputs(project_root=project_path, spec=spec)
            return "completed"
        if stage == Stage.novelty:
            refresh_novelty_map(project_root=project_path)
            return "completed"
        if stage == Stage.journal_fit:
            inspection = resolve_template(
                journal_family=state.journal_family,
                project_root=project_path,
                explicit_template=state.template_path,
            )
            write_text(project_path / "01_spec/journal_fit.md", render_inspection_markdown(inspection))
            if inspection.selected_path and inspection.main_tex and not state.template_path:
                state.template_path = inspection.selected_path
            status.blockers = [] if inspection.main_tex or state.journal_family == "custom" else inspection.notes
            return "completed"
        if stage == Stage.theory_program:
            generate_theory_program(project_root=project_path)
            return "completed"
        if stage == Stage.proof_audit:
            findings = generate_proof_audit(project_root=project_path)
            status.blockers = [f"{item.severity}:{item.title}" for item in findings if item.severity == "high"]
            return "completed"
        if stage == Stage.experiment_design:
            generate_experiment_plan(project_root=project_path)
            return "completed"
        if stage == Stage.scaffold_draft:
            main_tex_path = create_draft_scaffold(
                project_root=project_path,
                journal_family=state.journal_family,
                template_path=state.template_path,
            )
            status.blockers = []
            if not state.template_path:
                inspection = resolve_template(
                    journal_family=state.journal_family,
                    project_root=project_path,
                    explicit_template=state.template_path,
                )
                if inspection.selected_path:
                    state.template_path = inspection.selected_path
            write_text(
                project_path / "06_qa/qa_report.md",
                "# QA Report\n\n"
                f"- Draft scaffold generated: `{main_tex_path}`\n"
                f"- Stage: `scaffold_draft`\n",
            )
            return "completed"
        if stage == Stage.experiment_run:
            runner = TmuxRunner()
            runner.start_jobs(project_path)
            summary = runner.wait_for_quiescence(project_path)
            rows = write_results_audit(project_root=project_path)
            status.active_jobs = [
                JobStatus(job_id=job_id, tmux_session=f"gwmos-{job_id}", status=run_status)
                for job_id, run_status in sorted(summary.items())
            ]
            status.blockers = [
                row.note for row in rows if row.status in {"failed", "awaiting_script"}
            ] or ([] if any(value == "completed" for value in summary.values()) else ["Use `gw-mos exp start` to launch planned experiment jobs."])
            return "completed"
        if stage == Stage.alignment_review:
            rows = write_claim_evidence_matrix(project_root=project_path)
            pending = [row for row in rows if row.status != "pass"]
            status.blockers = [f"{row.claim_id}:{row.status}" for row in pending]
            return "completed"
        if stage == Stage.final_write:
            synthesis_pass(project_root=project_path)
            return "completed"
        if stage == Stage.build_qa:
            result = compile_project(project_root=project_path)
            write_qa_report(project_path / "06_qa/qa_report.md", result, project_root=project_path)
            readiness = write_submission_readiness(
                project_path / "06_qa/submission_readiness.md",
                project_root=project_path,
                compile_result=result,
            )
            build_submission_bundle(project_root=project_path, compile_result=result)
            status.last_build = {
                "status": "passed" if result.success else "failed",
                "engine": result.engine,
                "timestamp": result.ran_at,
                "pdf_path": result.pdf_path or "",
            }
            status.blockers = result.errors or readiness.blockers
            status.submission_ready = readiness.verdict
            return "completed" if result.success else "failed"
        return "completed"
