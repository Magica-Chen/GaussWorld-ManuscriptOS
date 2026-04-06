from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BuildPlan:
    engine: str
    commands: list[list[str]]
    missing_tools: list[str]


def latex_build_plan(main_tex: Path) -> BuildPlan:
    latexmk = shutil.which("latexmk")
    pdflatex = shutil.which("pdflatex")
    bibtex = shutil.which("bibtex")

    if latexmk:
        return BuildPlan(
            engine="latexmk",
            commands=[[latexmk, "-pdf", "-interaction=nonstopmode", "-halt-on-error", main_tex.name]],
            missing_tools=[],
        )

    if not pdflatex:
        return BuildPlan(engine="none", commands=[], missing_tools=["latexmk", "pdflatex"])

    commands = [[pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", main_tex.name]]
    if _needs_bibtex(main_tex):
        if not bibtex:
            return BuildPlan(engine="pdflatex", commands=commands, missing_tools=["bibtex"])
        stem = main_tex.stem
        commands.append([bibtex, stem])
        commands.append([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", main_tex.name])
    commands.append([pdflatex, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", main_tex.name])
    return BuildPlan(engine="pdflatex", commands=commands, missing_tools=[])


def _needs_bibtex(main_tex: Path) -> bool:
    content = main_tex.read_text(encoding="utf-8")
    return "\\bibliography{" in content
