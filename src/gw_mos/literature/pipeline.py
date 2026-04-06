from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from gw_mos.artifacts.models import CitationRecord, PaperSpec
from gw_mos.artifacts.writers import write_text
from gw_mos.literature.ingest_bib import ParsedBibEntry, ingest_bib
from gw_mos.literature.ingest_pdf import ingest_pdf
from gw_mos.literature.novelty import render_novelty_map
from gw_mos.literature.search import SearchResult, search_public_metadata
from gw_mos.utils.json_io import load_json, save_json


@dataclass(frozen=True)
class LiteratureIngestSummary:
    bib_files: int
    pdf_files: int
    grounded_entries: int
    provisional_entries: int
    notes_written: int


@dataclass(frozen=True)
class PublicSearchIngestSummary:
    query: str
    result_count: int
    grounded_entries: int
    notes_written: int


def ingest_literature(
    project_root: Path,
    bib_paths: list[Path] | None = None,
    pdf_paths: list[Path] | None = None,
) -> LiteratureIngestSummary:
    bib_paths = bib_paths or []
    pdf_paths = pdf_paths or []

    literature_root = project_root / "02_literature"
    notes_root = literature_root / "notes"
    bib_store_root = literature_root / "sources/bib"
    pdf_store_root = literature_root / "sources/pdf"
    notes_root.mkdir(parents=True, exist_ok=True)
    bib_store_root.mkdir(parents=True, exist_ok=True)
    pdf_store_root.mkdir(parents=True, exist_ok=True)

    existing_index = load_json(literature_root / "citation_index.json")
    citation_map = {
        item["id"]: CitationRecord.model_validate(item)
        for item in existing_index.get("papers", [])
    }

    library_path = literature_root / "library.bib"
    existing_library = library_path.read_text(encoding="utf-8") if library_path.exists() else ""
    existing_keys = _existing_bib_keys(existing_library)
    verified_entries: list[str] = []
    notes_written = 0
    grounded_entries = 0
    provisional_entries = 0

    for bib_path in bib_paths:
        target_path = bib_store_root / bib_path.name
        shutil.copy2(bib_path, target_path)
        for entry, metadata in ingest_bib(target_path):
            citation_map[metadata.record.id] = metadata.record
            notes_written += _write_bib_note(notes_root=notes_root, entry=entry, metadata=metadata, source_path=target_path)
            if metadata.record.verified and entry.key not in existing_keys:
                verified_entries.append(entry.raw.strip())
                existing_keys.add(entry.key)
            if metadata.record.verified:
                grounded_entries += 1
            else:
                provisional_entries += 1

    for pdf_path in pdf_paths:
        target_path = pdf_store_root / pdf_path.name
        shutil.copy2(pdf_path, target_path)
        metadata, extracted_text = ingest_pdf(target_path)
        citation_map[metadata.record.id] = metadata.record
        notes_written += _write_pdf_note(
            notes_root=notes_root,
            metadata=metadata,
            source_path=target_path,
            extracted_text=extracted_text,
        )
        provisional_entries += 1

    if verified_entries:
        separator = "\n\n" if existing_library.strip() else ""
        library_path.write_text(existing_library.rstrip() + separator + "\n\n".join(verified_entries).strip() + "\n", encoding="utf-8")
    elif not library_path.exists():
        library_path.write_text("% Grounded citations only.\n", encoding="utf-8")

    ordered = sorted(citation_map.values(), key=lambda item: ((item.year or 0) * -1, item.title.lower()))
    save_json(literature_root / "citation_index.json", {"papers": [item.model_dump(mode="json") for item in ordered]})
    write_text(literature_root / "novelty_map.md", render_novelty_map(project_root))

    return LiteratureIngestSummary(
        bib_files=len(bib_paths),
        pdf_files=len(pdf_paths),
        grounded_entries=grounded_entries,
        provisional_entries=provisional_entries,
        notes_written=notes_written,
    )


def refresh_novelty_map(project_root: Path) -> None:
    write_text(project_root / "02_literature/novelty_map.md", render_novelty_map(project_root))


def search_and_ingest_public_metadata(
    project_root: Path,
    query: str | None = None,
    limit: int = 6,
) -> PublicSearchIngestSummary:
    literature_root = project_root / "02_literature"
    notes_root = literature_root / "notes"
    notes_root.mkdir(parents=True, exist_ok=True)

    existing_index = load_json(literature_root / "citation_index.json")
    citation_map = {
        item["id"]: CitationRecord.model_validate(item)
        for item in existing_index.get("papers", [])
    }

    spec = _load_spec(project_root)
    resolved_query = query or _default_search_query(spec)
    results = search_public_metadata(query=resolved_query, limit=limit)

    library_path = literature_root / "library.bib"
    existing_library = library_path.read_text(encoding="utf-8") if library_path.exists() else ""
    existing_keys = _existing_bib_keys(existing_library)
    verified_entries: list[str] = []
    notes_written = 0
    grounded_entries = 0

    for result in results:
        record = CitationRecord(
            id=result.bibtex_key or _slug(result.title),
            title=result.title,
            authors=result.authors,
            year=result.year,
            source_type=result.source_type,
            source_url=result.source_url,
            bibtex_key=result.bibtex_key,
            verified=True,
            used_for_claims=[],
        )
        citation_map[record.id] = record
        if result.bibtex_key and result.bibtex_entry and result.bibtex_key not in existing_keys:
            verified_entries.append(result.bibtex_entry.strip())
            existing_keys.add(result.bibtex_key)
        notes_written += _write_public_search_note(notes_root=notes_root, result=result, query=resolved_query)
        grounded_entries += 1

    if verified_entries:
        separator = "\n\n" if existing_library.strip() else ""
        library_path.write_text(existing_library.rstrip() + separator + "\n\n".join(verified_entries).strip() + "\n", encoding="utf-8")
    elif not library_path.exists():
        library_path.write_text("% Grounded citations only.\n", encoding="utf-8")

    ordered = sorted(citation_map.values(), key=lambda item: ((item.year or 0) * -1, item.title.lower()))
    save_json(literature_root / "citation_index.json", {"papers": [item.model_dump(mode="json") for item in ordered]})
    write_text(literature_root / "public_search.md", render_public_search_report(query=resolved_query, results=results))
    write_text(literature_root / "novelty_map.md", render_novelty_map(project_root))
    return PublicSearchIngestSummary(
        query=resolved_query,
        result_count=len(results),
        grounded_entries=grounded_entries,
        notes_written=notes_written,
    )


def _existing_bib_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@") and "{" in stripped:
            before_comma = stripped.split("{", 1)[1]
            key = before_comma.split(",", 1)[0].strip()
            if key:
                keys.add(key)
    return keys


def _write_bib_note(notes_root: Path, entry: ParsedBibEntry, metadata, source_path: Path) -> int:
    note_path = notes_root / f"{entry.key}.md"
    authors = ", ".join(metadata.record.authors) if metadata.record.authors else "Unknown"
    lines = [
        f"# {metadata.record.title}",
        "",
        f"- Key: `{entry.key}`",
        f"- Source file: `{source_path}`",
        f"- Authors: {authors}",
        f"- Year: {metadata.record.year or 'unknown'}",
        f"- Grounded: `{metadata.record.verified}`",
        f"- Source type: `{metadata.record.source_type}`",
        f"- Source URL: `{metadata.record.source_url or 'n/a'}`",
        "",
        "## Notes",
    ]
    if metadata.notes:
        lines.extend(f"- {note}" for note in metadata.notes)
    else:
        lines.append("- Local BibTeX ingestion completed.")
    lines.extend(["", "## Next Actions", "- Link this source to specific claims in the claim-evidence matrix."])
    write_text(note_path, "\n".join(lines) + "\n")
    return 1


def _write_pdf_note(notes_root: Path, metadata, source_path: Path, extracted_text: str) -> int:
    note_path = notes_root / f"{metadata.record.id}.md"
    excerpt_lines = [line.strip() for line in extracted_text.splitlines() if line.strip()][:12]
    lines = [
        f"# {metadata.record.title}",
        "",
        f"- Source file: `{source_path}`",
        f"- Grounded: `{metadata.record.verified}`",
        f"- Source type: `{metadata.record.source_type}`",
        f"- Source URL: `{metadata.record.source_url or 'n/a'}`",
        "",
        "## Notes",
    ]
    if metadata.notes:
        lines.extend(f"- {note}" for note in metadata.notes)
    else:
        lines.append("- Local PDF ingestion completed.")
    lines.extend(["", "## Extracted Excerpt"])
    if excerpt_lines:
        lines.extend(excerpt_lines)
    else:
        lines.append("No text could be extracted from the local PDF.")
    write_text(note_path, "\n".join(lines) + "\n")
    return 1


def _write_public_search_note(notes_root: Path, result: SearchResult, query: str) -> int:
    note_path = notes_root / f"{result.bibtex_key or _slug(result.title)}.md"
    authors = ", ".join(result.authors) if result.authors else "Unknown"
    lines = [
        f"# {result.title}",
        "",
        f"- Query: `{query}`",
        f"- Source type: `{result.source_type}`",
        f"- Source URL: `{result.source_url}`",
        f"- Authors: {authors}",
        f"- Year: {result.year or 'unknown'}",
        f"- BibTeX key: `{result.bibtex_key or 'n/a'}`",
        "",
        "## Notes",
        "- Added from public metadata search.",
        "- Verify the claim-level relevance before citing this paper in the manuscript.",
    ]
    if result.abstract:
        lines.extend(["", "## Abstract Excerpt", result.abstract[:1200]])
    write_text(note_path, "\n".join(lines) + "\n")
    return 1


def render_public_search_report(query: str, results: list[SearchResult]) -> str:
    lines = [
        "# Public Metadata Search",
        "",
        f"- Query: `{query}`",
        f"- Results added: `{len(results)}`",
        "",
        "## Results",
    ]
    if not results:
        lines.append("- No public metadata results were returned.")
    for result in results:
        lines.append(
            f"- `{result.bibtex_key or _slug(result.title)}` ({result.year or 'unknown'}) {result.title} [{result.source_type}: {result.source_url}]"
        )
    return "\n".join(lines) + "\n"


def _load_spec(project_root: Path) -> PaperSpec:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    return PaperSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))


def _default_search_query(spec: PaperSpec) -> str:
    components = [spec.title_working, spec.problem_statement, *(claim.text for claim in spec.core_claims[:2])]
    text = " ".join(component for component in components if component).strip()
    return " ".join(text.split()[:24]) or "research paper theory experiment"


def _slug(text: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in text).strip("_")[:40] or "citation"
