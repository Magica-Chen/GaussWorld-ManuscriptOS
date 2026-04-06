from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gw_mos.literature.metadata import CitationMetadata, citation_from_bib_fields


@dataclass(frozen=True)
class ParsedBibEntry:
    entry_type: str
    key: str
    fields: dict[str, str]
    raw: str


def ingest_bib(path: Path) -> list[tuple[ParsedBibEntry, CitationMetadata]]:
    text = path.read_text(encoding="utf-8")
    entries = parse_bibtex_entries(text)
    return [(entry, citation_from_bib_fields(entry.key, entry.fields)) for entry in entries]


def parse_bibtex_entries(text: str) -> list[ParsedBibEntry]:
    entries: list[ParsedBibEntry] = []
    cursor = 0
    while True:
        start = text.find("@", cursor)
        if start == -1:
            break
        header_end = text.find("{", start)
        alt_header_end = text.find("(", start)
        if header_end == -1 or (alt_header_end != -1 and alt_header_end < header_end):
            header_end = alt_header_end
            open_char, close_char = "(", ")"
        else:
            open_char, close_char = "{", "}"
        if header_end == -1:
            break
        entry_type = text[start + 1 : header_end].strip().lower()
        end = _find_matching_delimiter(text, header_end, open_char, close_char)
        raw = text[start : end + 1].strip()
        inner = text[header_end + 1 : end].strip()
        key, fields_block = _split_key_and_fields(inner)
        fields = _parse_fields(fields_block)
        entries.append(ParsedBibEntry(entry_type=entry_type, key=key, fields=fields, raw=raw))
        cursor = end + 1
    return entries


def _find_matching_delimiter(text: str, open_index: int, open_char: str, close_char: str) -> int:
    depth = 0
    in_quote = False
    escape = False
    for index in range(open_index, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Unbalanced BibTeX entry.")


def _split_key_and_fields(inner: str) -> tuple[str, str]:
    depth = 0
    in_quote = False
    escape = False
    for index, char in enumerate(inner):
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            return inner[:index].strip(), inner[index + 1 :].strip()
    return inner.strip(), ""


def _parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    cursor = 0
    while cursor < len(block):
        while cursor < len(block) and block[cursor] in " \t\r\n,":
            cursor += 1
        if cursor >= len(block):
            break
        name_start = cursor
        while cursor < len(block) and block[cursor] not in "=":
            cursor += 1
        field_name = block[name_start:cursor].strip().lower()
        if cursor >= len(block):
            break
        cursor += 1
        while cursor < len(block) and block[cursor].isspace():
            cursor += 1
        if cursor >= len(block):
            fields[field_name] = ""
            break
        if block[cursor] == "{":
            value, cursor = _consume_braced_value(block, cursor)
        elif block[cursor] == '"':
            value, cursor = _consume_quoted_value(block, cursor)
        else:
            value_start = cursor
            while cursor < len(block) and block[cursor] not in ",\n":
                cursor += 1
            value = block[value_start:cursor].strip()
        fields[field_name] = value.strip()
    return fields


def _consume_braced_value(text: str, cursor: int) -> tuple[str, int]:
    depth = 0
    start = cursor
    for index in range(cursor, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1], index + 1
    raise ValueError("Unbalanced braced field.")


def _consume_quoted_value(text: str, cursor: int) -> tuple[str, int]:
    start = cursor
    escape = False
    for index in range(cursor + 1, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            return text[start : index + 1], index + 1
    raise ValueError("Unbalanced quoted field.")
