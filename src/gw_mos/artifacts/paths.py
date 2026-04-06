from __future__ import annotations

from pathlib import Path


PROJECT_DIRECTORIES = (
    "00_intake",
    "01_spec",
    "02_literature/notes",
    "02_literature/sources/bib",
    "02_literature/sources/pdf",
    "03_theory",
    "04_experiments/jobs",
    "04_experiments/scripts",
    "04_experiments/generated",
    "04_experiments/outputs",
    "05_draft/sections",
    "05_draft/figures",
    "05_draft/tables",
    "06_qa",
    "07_submission",
    "runtime",
    "disputes",
)


def ensure_project_directories(project_root: Path) -> None:
    for relative in PROJECT_DIRECTORIES:
        (project_root / relative).mkdir(parents=True, exist_ok=True)
