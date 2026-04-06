from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class TemplateInspection(BaseModel):
    requested_family: str
    resolved_family: str
    selected_path: str | None = None
    template_name: str | None = None
    main_tex: list[str] = Field(default_factory=list)
    class_files: list[str] = Field(default_factory=list)
    bst_files: list[str] = Field(default_factory=list)
    bib_files: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)


PRIORITY_TEX_NAMES = (
    "main.tex",
    "template.tex",
    "sn-article.tex",
    "elsarticle-template-num.tex",
    "elsarticle-template-num-names.tex",
    "elsarticle-template-harv.tex",
)


def resolve_template(
    journal_family: str,
    project_root: Path,
    explicit_template: str | None = None,
    search_root: Path | None = None,
) -> TemplateInspection:
    root = (search_root or Path.cwd()).resolve()
    explicit_path = _normalize_explicit_template(explicit_template, project_root, root)
    if explicit_path:
        return inspect_template_path(explicit_path, requested_family=journal_family)

    family = journal_family if journal_family in {"elsevier", "springer_nature"} else "custom"
    candidates = _family_candidate_dirs(family=family, project_root=project_root, search_root=root)
    if not candidates:
        return TemplateInspection(
            requested_family=journal_family,
            resolved_family=family,
            notes=[f"No local template directory found for family '{journal_family}'."],
        )

    inspected = [inspect_template_path(candidate, requested_family=journal_family) for candidate in candidates]
    if family == "custom":
        custom_only = [item for item in inspected if item.resolved_family == "custom"]
        selected = _pick_best_inspection(custom_only or inspected)
    else:
        selected = _pick_best_inspection(inspected)
    if family == "custom" and selected.resolved_family in {"elsevier", "springer_nature"}:
        selected.resolved_family = selected.resolved_family
    else:
        selected.resolved_family = family
    selected.candidates = [str(path) for path in candidates]
    if not selected.main_tex:
        selected.notes.append("No viable template with a main .tex file was found among local candidates.")
    return selected


def inspect_template_path(path: Path, requested_family: str) -> TemplateInspection:
    if path.is_file():
        path = path.parent
    files = sorted(file for file in path.rglob("*") if file.is_file() and ":Zone.Identifier" not in file.name)
    tex_files = [str(file.relative_to(path)) for file in files if file.suffix == ".tex"]
    class_files = [str(file.relative_to(path)) for file in files if file.suffix == ".cls"]
    bst_files = [str(file.relative_to(path)) for file in files if file.suffix == ".bst"]
    bib_files = [str(file.relative_to(path)) for file in files if file.suffix == ".bib"]
    main_tex = _sort_tex_files(tex_files)

    notes: list[str] = []
    if not tex_files:
        notes.append("No .tex file found in template directory.")
    if class_files:
        notes.append("Class file(s) detected.")
    if bst_files:
        notes.append("Bibliography style file(s) detected.")

    return TemplateInspection(
        requested_family=requested_family,
        resolved_family=_infer_family_from_path(path),
        selected_path=str(path),
        template_name=path.name,
        main_tex=main_tex,
        class_files=class_files,
        bst_files=bst_files,
        bib_files=bib_files,
        notes=notes,
    )


def render_inspection_markdown(inspection: TemplateInspection) -> str:
    lines = [
        "# Journal Fit",
        "",
        f"- Requested family: `{inspection.requested_family}`",
        f"- Resolved family: `{inspection.resolved_family}`",
        f"- Selected template path: `{inspection.selected_path or 'not found'}`",
        f"- Template name: `{inspection.template_name or 'unknown'}`",
        "",
        "## Template Files",
    ]
    if inspection.main_tex:
        lines.extend(f"- main tex: `{item}`" for item in inspection.main_tex)
    else:
        lines.append("- main tex: none found")
    if inspection.class_files:
        lines.extend(f"- class file: `{item}`" for item in inspection.class_files)
    if inspection.bst_files:
        lines.extend(f"- bst file: `{item}`" for item in inspection.bst_files)
    if inspection.bib_files:
        lines.extend(f"- bib file: `{item}`" for item in inspection.bib_files)
    if inspection.candidates:
        lines.extend(["", "## Candidate Directories"])
        lines.extend(f"- `{candidate}`" for candidate in inspection.candidates)
    if inspection.notes:
        lines.extend(["", "## Notes"])
        lines.extend(f"- {note}" for note in inspection.notes)
    return "\n".join(lines) + "\n"


def _normalize_explicit_template(explicit_template: str | None, project_root: Path, search_root: Path) -> Path | None:
    if not explicit_template:
        return None
    candidate = Path(explicit_template).expanduser()
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (project_root, search_root):
        resolved = (base / candidate).resolve()
        if resolved.exists():
            return resolved
    return None


def _family_candidate_dirs(family: str, project_root: Path, search_root: Path) -> list[Path]:
    raw_candidates: list[Path] = []
    if family == "elsevier":
        raw_candidates.extend([search_root / "elsarticle", project_root / "elsarticle", search_root / "vendor/elsevier"])
    elif family == "springer_nature":
        raw_candidates.extend(
            [search_root / "sn-article-template", project_root / "sn-article-template", search_root / "vendor/springer_nature"]
        )
    else:
        raw_candidates.extend(_discover_custom_candidates(project_root=project_root, search_root=search_root))
    seen: set[Path] = set()
    existing: list[Path] = []
    for candidate in raw_candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            existing.append(resolved)
    return existing


def _discover_custom_candidates(project_root: Path, search_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for base in (project_root, search_root):
        journal_dir = base / "journal"
        if journal_dir.exists() and journal_dir.is_dir():
            for child in sorted(journal_dir.iterdir()):
                if child.is_dir():
                    candidates.append(child)
        templates_dir = base / "templates"
        if templates_dir.exists() and templates_dir.is_dir():
            for child in sorted(templates_dir.iterdir()):
                if child.is_dir():
                    candidates.append(child)
    custom_example = search_root / "vendor/custom_examples/jasa"
    if custom_example.exists():
        candidates.append(custom_example)
    return candidates


def _sort_tex_files(tex_files: list[str]) -> list[str]:
    def priority(name: str) -> tuple[int, str]:
        try:
            return (PRIORITY_TEX_NAMES.index(Path(name).name), name)
        except ValueError:
            return (len(PRIORITY_TEX_NAMES), name)

    return sorted(tex_files, key=priority)


def _infer_family_from_path(path: Path) -> str:
    lowered = str(path).lower()
    if "elsarticle" in lowered or "elsevier" in lowered:
        return "elsevier"
    if "sn-article" in lowered or "springer" in lowered:
        return "springer_nature"
    return "custom"


def _pick_best_inspection(inspections: list[TemplateInspection]) -> TemplateInspection:
    def score(inspection: TemplateInspection) -> tuple[int, int, int, int]:
        return (
            1 if inspection.main_tex else 0,
            len(inspection.class_files),
            len(inspection.bst_files),
            len(inspection.bib_files),
        )

    return max(inspections, key=score)
