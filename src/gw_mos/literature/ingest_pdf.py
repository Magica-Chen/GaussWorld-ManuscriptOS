from __future__ import annotations

import shutil
from pathlib import Path

from gw_mos.literature.metadata import CitationMetadata, citation_from_pdf_text
from gw_mos.utils.subprocess import run_command


def ingest_pdf(path: Path) -> tuple[CitationMetadata, str]:
    text = extract_pdf_text(path)
    metadata = citation_from_pdf_text(stem=path.stem, text=text)
    return metadata, text


def extract_pdf_text(path: Path, max_pages: int = 2) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""
    completed = run_command([pdftotext, "-f", "1", "-l", str(max_pages), str(path), "-"])
    if completed.returncode != 0:
        return ""
    return completed.stdout
