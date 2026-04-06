from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gw_mos.controller.engine import ControllerEngine
from gw_mos.nl import execute_request, help_text


@dataclass
class OrchestratorReply:
    output: str
    exit_session: bool = False


class GwMosOrchestrator:
    def __init__(
        self,
        *,
        project: Path | None = None,
        root: Path = Path("."),
        journal: str = "custom",
        template: Path | None = None,
    ) -> None:
        self.current_project = project
        self.root = root
        self.journal = journal
        self.template = template
        self.engine = ControllerEngine()

    def handle(self, request: str) -> OrchestratorReply:
        text = request.strip()
        if not text:
            return OrchestratorReply(output="")
        if text.startswith("/"):
            return self._handle_slash_command(text)

        result = execute_request(
            request=text,
            project_path=self.current_project,
            root=self.root,
            journal=self.journal,
            template=self.template,
        )
        self.current_project = result.project_path or self.current_project
        return OrchestratorReply(output=result.output.rstrip())

    def shell_status(self) -> str:
        project = str(self.current_project) if self.current_project else "none"
        return f"project={project} | root={self.root} | journal={self.journal}"

    def _handle_slash_command(self, text: str) -> OrchestratorReply:
        command, _, argument = text.partition(" ")
        arg = argument.strip()

        if command in {"/exit", "/quit"}:
            return OrchestratorReply(output="Leaving gw-mos interactive session.", exit_session=True)
        if command == "/help":
            return OrchestratorReply(output=shell_help_text())
        if command == "/status":
            if self.current_project is None:
                return OrchestratorReply(output="No project selected.")
            return OrchestratorReply(output=self.engine.render_status(self.current_project))
        if command == "/next":
            if self.current_project is None:
                return OrchestratorReply(output="No project selected.")
            result = execute_request(
                request="go to next",
                project_path=self.current_project,
                root=self.root,
                journal=self.journal,
                template=self.template,
            )
            self.current_project = result.project_path or self.current_project
            return OrchestratorReply(output=result.output.rstrip())
        if command == "/ready":
            if self.current_project is None:
                return OrchestratorReply(output="No project selected.")
            result = execute_request(
                request="prepare the paper to be submission ready",
                project_path=self.current_project,
                root=self.root,
                journal=self.journal,
                template=self.template,
            )
            self.current_project = result.project_path or self.current_project
            return OrchestratorReply(output=result.output.rstrip())
        if command == "/qa":
            if self.current_project is None:
                return OrchestratorReply(output="No project selected.")
            report_path = self.current_project / "06_qa/qa_report.md"
            if not report_path.exists():
                return OrchestratorReply(output="No QA report found. Run `/ready` or ask to build the PDF first.")
            return OrchestratorReply(output=report_path.read_text(encoding="utf-8").strip())
        if command == "/bundle":
            if self.current_project is None:
                return OrchestratorReply(output="No project selected.")
            manifest_path = self.current_project / "07_submission/manifest.md"
            if not manifest_path.exists():
                return OrchestratorReply(output="No submission bundle found. Run `/ready` or build the paper first.")
            return OrchestratorReply(output=manifest_path.read_text(encoding="utf-8").strip())
        if command == "/artifacts":
            if self.current_project is None:
                return OrchestratorReply(output="No project selected.")
            return OrchestratorReply(output=_artifact_summary(self.current_project))
        if command in {"/show", "/cat"}:
            if self.current_project is None:
                return OrchestratorReply(output="No project selected.")
            if not arg:
                return OrchestratorReply(output="Usage: /show <relative-path>")
            target = (self.current_project / arg).resolve()
            if not target.exists():
                return OrchestratorReply(output=f"Path not found: {target}")
            if target.is_dir():
                entries = sorted(path.name for path in target.iterdir())
                return OrchestratorReply(output="\n".join(entries))
            content = target.read_text(encoding="utf-8", errors="replace")
            preview = "\n".join(content.splitlines()[:80])
            return OrchestratorReply(output=preview)
        if command == "/project":
            if not arg:
                current = self.current_project or "none"
                return OrchestratorReply(output=f"current_project={current}")
            candidate = Path(arg).expanduser()
            if not candidate.is_absolute():
                candidate = (Path.cwd() / candidate).resolve()
            if not candidate.exists():
                return OrchestratorReply(output=f"Project path not found: {candidate}")
            self.current_project = candidate
            return OrchestratorReply(output=f"Active project set to {candidate}")
        if command == "/root":
            if not arg:
                return OrchestratorReply(output=f"root={self.root}")
            self.root = Path(arg).expanduser().resolve()
            return OrchestratorReply(output=f"Root set to {self.root}")
        if command == "/journal":
            if not arg:
                return OrchestratorReply(output=f"journal={self.journal}")
            self.journal = arg
            return OrchestratorReply(output=f"Default journal set to {self.journal}")
        if command == "/new":
            if not arg:
                return OrchestratorReply(output="Usage: /new <project_name>")
            result = execute_request(
                request=f"create a new project called {arg} for {self.journal}",
                project_path=None,
                root=self.root,
                journal=self.journal,
                template=self.template,
            )
            self.current_project = result.project_path
            return OrchestratorReply(output=result.output.rstrip())

        return OrchestratorReply(output=f"Unknown command: {command}\n\n{shell_help_text()}")


def shell_help_text() -> str:
    return (
        "Interactive commands:\n"
        "/help                Show shell commands and NL examples\n"
        "/status              Show current project status\n"
        "/next                Run the next workflow step\n"
        "/ready               Run the full submission-ready pipeline\n"
        "/qa                  Show the latest QA report\n"
        "/bundle              Show the latest submission bundle manifest\n"
        "/artifacts           List key project artifacts\n"
        "/show <path>         Show a file preview relative to the project root\n"
        "/project <path>      Switch active project\n"
        "/project             Show active project\n"
        "/root <path>         Set default root for new projects\n"
        "/journal <name>      Set default journal family for new projects\n"
        "/new <name>          Create a new project\n"
        "/exit                Leave the session\n\n"
        + help_text()
    )


def _artifact_summary(project_root: Path) -> str:
    candidates = [
        "00_intake/idea.md",
        "01_spec/paper_spec.yaml",
        "01_spec/contribution_hypotheses.md",
        "02_literature/novelty_map.md",
        "02_literature/public_search.md",
        "03_theory/theorem_ledger.md",
        "03_theory/proof_audit.md",
        "04_experiments/experiment_plan.md",
        "04_experiments/results_audit.md",
        "05_draft/main.tex",
        "06_qa/qa_report.md",
        "06_qa/submission_readiness.md",
        "07_submission/manifest.md",
    ]
    lines = ["Key artifacts:"]
    for relative in candidates:
        path = project_root / relative
        if path.exists():
            lines.append(f"- {relative}")
    return "\n".join(lines)
