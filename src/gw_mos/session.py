from __future__ import annotations

from pathlib import Path

from gw_mos.orchestrator import GwMosOrchestrator
from gw_mos.tui import render_banner, render_prompt


def start_interactive_session(
    *,
    project: Path | None = None,
    root: Path = Path("."),
    journal: str = "custom",
    template: Path | None = None,
) -> None:
    orchestrator = GwMosOrchestrator(project=project, root=root, journal=journal, template=template)
    print(render_banner(orchestrator.current_project), end="")
    while True:
        try:
            request = input(render_prompt(orchestrator.current_project))
        except EOFError:
            print()
            break
        reply = orchestrator.handle(request)
        if reply.output:
            print(reply.output)
        if reply.exit_session:
            break
