from __future__ import annotations

from pathlib import Path


def render_banner(project: Path | None) -> str:
    project_label = str(project) if project else "none"
    return (
        "gw-mos interactive session\n"
        "Natural-language paper completion shell\n"
        f"active_project={project_label}\n"
        "Type /help for shell commands, /ready for the full pipeline, or describe the next paper task.\n"
    )


def render_prompt(project: Path | None) -> str:
    if project is None:
        return "gw-mos> "
    return f"gw-mos[{project.name}]> "
