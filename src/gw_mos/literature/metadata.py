from __future__ import annotations

import re
from dataclasses import dataclass

from gw_mos.artifacts.models import CitationRecord

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
ARXIV_RE = re.compile(r"(?:arXiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


@dataclass(frozen=True)
class CitationMetadata:
    record: CitationRecord
    grounded: bool
    notes: list[str]


def citation_from_bib_fields(key: str, fields: dict[str, str]) -> CitationMetadata:
    title = _clean_field(fields.get("title", ""))
    authors = _parse_authors(fields.get("author", ""))
    year = _parse_year(fields.get("year", ""))
    doi = _clean_field(fields.get("doi", ""))
    url = _clean_field(fields.get("url", ""))
    eprint = _clean_field(fields.get("eprint", ""))
    archive_prefix = _clean_field(fields.get("archiveprefix", ""))

    notes: list[str] = []
    source_type = "local_bib"
    source_url = ""
    grounded = False
    if doi:
        grounded = True
        source_type = "doi"
        source_url = f"https://doi.org/{doi}"
    elif archive_prefix.lower() == "arxiv" and eprint:
        grounded = True
        source_type = "arxiv"
        source_url = f"https://arxiv.org/abs/{eprint}"
    elif eprint and ARXIV_RE.search(eprint):
        grounded = True
        source_type = "arxiv"
        source_url = f"https://arxiv.org/abs/{ARXIV_RE.search(eprint).group(1)}"
    elif url:
        grounded = True
        source_type = "url"
        source_url = url
    else:
        notes.append("BibTeX entry is missing DOI, arXiv identifier, or URL.")

    if not title:
        notes.append("BibTeX entry is missing a title.")
    if not authors:
        notes.append("BibTeX entry is missing authors.")
    if year is None:
        notes.append("BibTeX entry is missing a parseable year.")

    record = CitationRecord(
        id=key,
        title=title or key,
        authors=authors,
        year=year,
        source_type=source_type,
        source_url=source_url,
        bibtex_key=key,
        verified=grounded and bool(title and year),
        used_for_claims=[],
    )
    return CitationMetadata(record=record, grounded=grounded, notes=notes)


def citation_from_pdf_text(stem: str, text: str) -> CitationMetadata:
    title = extract_pdf_title(text=text, fallback=stem)
    doi_match = DOI_RE.search(text)
    arxiv_match = ARXIV_RE.search(text)
    year_match = YEAR_RE.search(text)

    notes: list[str] = []
    source_type = "local_pdf"
    source_url = ""
    if doi_match:
        source_type = "doi"
        source_url = f"https://doi.org/{doi_match.group(0)}"
        notes.append("Detected DOI in local PDF text.")
    elif arxiv_match:
        source_type = "arxiv"
        source_url = f"https://arxiv.org/abs/{arxiv_match.group(1)}"
        notes.append("Detected arXiv identifier in local PDF text.")
    else:
        notes.append("No DOI or arXiv identifier detected in local PDF text.")

    year = int(year_match.group(0)) if year_match else None
    if year is None:
        notes.append("No parseable year detected in local PDF text.")

    record = CitationRecord(
        id=_slugify(stem),
        title=title,
        authors=[],
        year=year,
        source_type=source_type,
        source_url=source_url,
        bibtex_key="",
        verified=False,
        used_for_claims=[],
    )
    return CitationMetadata(record=record, grounded=False, notes=notes)


def extract_pdf_title(text: str, fallback: str) -> str:
    candidates = [line.strip() for line in text.splitlines() if line.strip()]
    for line in candidates:
        if len(line) < 8:
            continue
        if line.lower().startswith(("arxiv", "submitted", "accepted", "journal", "doi")):
            continue
        if line.count(" ") > 20:
            continue
        return _clean_field(line)
    return fallback.replace("_", " ").replace("-", " ").title()


def _parse_authors(raw: str) -> list[str]:
    value = _clean_field(raw)
    if not value:
        return []
    return [author.strip() for author in value.replace("\n", " ").split(" and ") if author.strip()]


def _parse_year(raw: str) -> int | None:
    match = YEAR_RE.search(raw)
    if not match:
        return None
    return int(match.group(0))


def _clean_field(value: str) -> str:
    cleaned = value.strip().strip(",")
    if cleaned.startswith("{") and cleaned.endswith("}"):
        cleaned = cleaned[1:-1]
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]
    cleaned = cleaned.replace("\n", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return slug or "citation"
