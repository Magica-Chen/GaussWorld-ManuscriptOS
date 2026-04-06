from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    source_url: str
    source_type: str
    authors: list[str] = []
    year: int | None = None
    bibtex_key: str = ""
    bibtex_entry: str = ""
    abstract: str = ""


@dataclass(frozen=True)
class SearchSummary:
    query: str
    results: list[SearchResult]


def search_public_metadata(query: str, limit: int = 6) -> list[SearchResult]:
    results = [*search_crossref(query=query, limit=max(1, limit // 2 + limit % 2)), *search_arxiv(query=query, limit=max(1, limit // 2))]
    deduped: list[SearchResult] = []
    seen_titles: set[str] = set()
    for result in results:
        normalized = _normalize_title(result.title)
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        deduped.append(result)
    return deduped[:limit]


def search_crossref(query: str, limit: int = 3) -> list[SearchResult]:
    url = (
        "https://api.crossref.org/works?"
        f"query.bibliographic={quote_plus(query)}&rows={limit}"
        "&select=DOI,title,author,issued,URL,type,container-title"
    )
    payload = _get_json(url, headers={"User-Agent": "gw-mos/0.1.0 (public metadata lookup)"})
    items = payload.get("message", {}).get("items", [])
    results: list[SearchResult] = []
    for item in items:
        title = ((item.get("title") or [""]) or [""])[0].strip()
        if not title:
            continue
        authors = [
            " ".join(part for part in (author.get("given", ""), author.get("family", "")) if part).strip()
            for author in item.get("author", [])
        ]
        year = _extract_crossref_year(item)
        doi = item.get("DOI", "")
        source_url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
        bibtex_key = _make_bibtex_key(authors=authors, year=year, title=title)
        bibtex_entry = _crossref_bibtex(item=item, title=title, authors=authors, year=year, key=bibtex_key)
        results.append(
            SearchResult(
                title=title,
                source_url=source_url,
                source_type="doi" if doi else "url",
                authors=[author for author in authors if author],
                year=year,
                bibtex_key=bibtex_key,
                bibtex_entry=bibtex_entry,
            )
        )
    return results


def search_arxiv(query: str, limit: int = 3) -> list[SearchResult]:
    url = f"https://export.arxiv.org/api/query?search_query=all:{quote_plus(query)}&start=0&max_results={limit}"
    xml_text = _get_text(url, headers={"User-Agent": "gw-mos/0.1.0 (public metadata lookup)"})
    root = ET.fromstring(xml_text)
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    results: list[SearchResult] = []
    for entry in root.findall("atom:entry", namespace):
        title = _clean_space(entry.findtext("atom:title", default="", namespaces=namespace))
        if not title:
            continue
        source_url = entry.findtext("atom:id", default="", namespaces=namespace).strip()
        authors = [_clean_space(node.text or "") for node in entry.findall("atom:author/atom:name", namespace)]
        published = entry.findtext("atom:published", default="", namespaces=namespace)
        year = int(published[:4]) if len(published) >= 4 and published[:4].isdigit() else None
        summary = _clean_space(entry.findtext("atom:summary", default="", namespaces=namespace))
        bibtex_key = _make_bibtex_key(authors=authors, year=year, title=title)
        bibtex_entry = _arxiv_bibtex(title=title, authors=authors, year=year, source_url=source_url, key=bibtex_key)
        results.append(
            SearchResult(
                title=title,
                source_url=source_url,
                source_type="arxiv",
                authors=[author for author in authors if author],
                year=year,
                bibtex_key=bibtex_key,
                bibtex_entry=bibtex_entry,
                abstract=summary,
            )
        )
    return results


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    return json.loads(_get_text(url, headers=headers))


def _get_text(url: str, headers: dict[str, str] | None = None) -> str:
    request = Request(url, method="GET")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Public literature search failed: {exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Public literature search failed: {exc.reason}") from exc


def _extract_crossref_year(item: dict) -> int | None:
    for field in ("issued", "published-print", "published-online", "created"):
        parts = item.get(field, {}).get("date-parts", [])
        if parts and parts[0]:
            value = parts[0][0]
            if isinstance(value, int):
                return value
    return None


def _crossref_bibtex(item: dict, title: str, authors: list[str], year: int | None, key: str) -> str:
    doi = item.get("DOI", "")
    journal = ((item.get("container-title") or [""]) or [""])[0]
    author_field = " and ".join(_bibtex_author(author) for author in authors if author)
    lines = [f"@article{{{key},"]
    lines.append(f"  title = {{{title}}},")
    if author_field:
        lines.append(f"  author = {{{author_field}}},")
    if journal:
        lines.append(f"  journal = {{{journal}}},")
    if year is not None:
        lines.append(f"  year = {{{year}}},")
    if doi:
        lines.append(f"  doi = {{{doi}}},")
    url = item.get("URL", "")
    if url:
        lines.append(f"  url = {{{url}}},")
    lines.append("}")
    return "\n".join(lines)


def _arxiv_bibtex(title: str, authors: list[str], year: int | None, source_url: str, key: str) -> str:
    author_field = " and ".join(_bibtex_author(author) for author in authors if author)
    arxiv_id = source_url.rstrip("/").split("/")[-1]
    lines = [f"@misc{{{key},"]
    lines.append(f"  title = {{{title}}},")
    if author_field:
        lines.append(f"  author = {{{author_field}}},")
    if year is not None:
        lines.append(f"  year = {{{year}}},")
    if arxiv_id:
        lines.append(f"  eprint = {{{arxiv_id}}},")
        lines.append("  archivePrefix = {arXiv},")
    if source_url:
        lines.append(f"  url = {{{source_url}}},")
    lines.append("}")
    return "\n".join(lines)


def _make_bibtex_key(authors: list[str], year: int | None, title: str) -> str:
    author_token = "anon"
    if authors:
        surname = authors[0].split()[-1]
        author_token = re.sub(r"[^A-Za-z0-9]+", "", surname).lower() or "anon"
    title_token = re.sub(r"[^A-Za-z0-9]+", "", "".join(title.split()[:2])).lower() or "work"
    year_token = str(year) if year is not None else "nd"
    return f"{author_token}{year_token}{title_token[:12]}"


def _bibtex_author(author: str) -> str:
    parts = author.split()
    if len(parts) < 2:
        return author
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def _clean_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
