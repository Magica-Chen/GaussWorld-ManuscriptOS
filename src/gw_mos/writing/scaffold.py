from __future__ import annotations

import re
import shutil
from pathlib import Path

import yaml

from gw_mos.artifacts.models import PaperSpec
from gw_mos.artifacts.readers import read_text
from gw_mos.artifacts.writers import write_text
from gw_mos.journals.discovery import TemplateInspection, resolve_template

SKIP_SUFFIXES = {
    ".aux",
    ".bbl",
    ".bcf",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".run.xml",
    ".synctex.gz",
}

MANAGED_SECTION_BEGIN = "% gw-mos managed sections begin"
MANAGED_SECTION_END = "% gw-mos managed sections end"


def scaffold_sections(spec: PaperSpec) -> list[tuple[str, str, str]]:
    sections: list[tuple[str, str, str]] = [
        ("introduction", "Introduction", _introduction_body(spec)),
        ("related_work", "Related Work", _related_work_body(spec)),
        ("theory", "Theoretical Results", _theory_body(spec)),
    ]
    if "experiment" in spec.contribution_type:
        sections.append(("experiments", "Experiments", _experiments_body(spec)))
    sections.extend(
        [
            ("discussion", "Discussion", _discussion_body(spec)),
            ("conclusion", "Conclusion", _conclusion_body(spec)),
        ]
    )
    return sections


def create_draft_scaffold(
    project_root: Path,
    journal_family: str,
    template_path: str | None = None,
) -> Path:
    draft_root = project_root / "05_draft"
    spec = _load_spec(project_root)
    inspection = resolve_template(
        journal_family=journal_family,
        project_root=project_root,
        explicit_template=template_path,
    )
    copied_files = _copy_template_assets(draft_root=draft_root, inspection=inspection)
    section_specs = scaffold_sections(spec)
    _write_sections(draft_root=draft_root, section_specs=section_specs)

    mode = _select_scaffold_mode(journal_family=journal_family, inspection=inspection)
    main_tex_path = draft_root / "main.tex"
    if mode == "elsevier":
        main_text = _render_elsevier_main(spec=spec, section_specs=section_specs, inspection=inspection)
        _write_managed_main(main_tex_path, main_text)
    elif mode == "springer_nature":
        main_text = _render_springer_main(spec=spec, section_specs=section_specs, inspection=inspection)
        _write_managed_main(main_tex_path, main_text)
    elif mode == "custom_copy":
        source_rel = inspection.main_tex[0]
        source_path = draft_root / source_rel
        if not source_path.exists() and source_rel == "main.tex":
            source_path = draft_root / "template_main_source.tex"
        if source_path.resolve() != main_tex_path.resolve():
            shutil.copy2(source_path, main_tex_path)
        _patch_custom_main(main_tex_path=main_tex_path, spec=spec, section_specs=section_specs)
    else:
        main_text = _render_generic_main(spec=spec, section_specs=section_specs, inspection=inspection)
        _write_managed_main(main_tex_path, main_text)

    manifest = {
        "journal_family": journal_family,
        "scaffold_mode": mode,
        "template_path": inspection.selected_path,
        "template_name": inspection.template_name,
        "main_tex_candidates": inspection.main_tex,
        "copied_files": copied_files,
        "section_files": [f"sections/{slug}.tex" for slug, _, _ in section_specs],
    }
    write_text(draft_root / "template_manifest.yaml", yaml.safe_dump(manifest, sort_keys=False))
    write_text(draft_root / "sections/README.md", _sections_readme(mode=mode, spec=spec))
    return main_tex_path


def _load_spec(project_root: Path) -> PaperSpec:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    return PaperSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))


def _copy_template_assets(draft_root: Path, inspection: TemplateInspection) -> list[str]:
    if not inspection.selected_path:
        return []
    source_root = Path(inspection.selected_path)
    if not source_root.exists():
        return []
    copied: list[str] = []
    for source in sorted(source_root.rglob("*")):
        if source.is_dir():
            continue
        if _should_skip_template_file(source):
            continue
        rel = source.relative_to(source_root)
        destination = draft_root / rel
        if rel.as_posix() == "main.tex":
            destination = draft_root / "template_main_source.tex"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        copied.append(str(destination.relative_to(draft_root)))
    return copied


def _should_skip_template_file(path: Path) -> bool:
    name = path.name
    if ":Zone.Identifier" in name:
        return True
    if name.endswith(".synctex.gz"):
        return True
    if any(name.endswith(suffix) for suffix in SKIP_SUFFIXES):
        return True
    return False


def _write_sections(draft_root: Path, section_specs: list[tuple[str, str, str]]) -> None:
    for slug, title, body in section_specs:
        content = f"% gw-mos scaffold section\n\\section{{{title}}}\n\\label{{sec:{slug.replace('_', '-')}}}\n\n{body}\n"
        write_text(draft_root / f"sections/{slug}.tex", content)


def _select_scaffold_mode(journal_family: str, inspection: TemplateInspection) -> str:
    resolved_family = inspection.resolved_family or journal_family
    if resolved_family == "elsevier":
        return "elsevier"
    if resolved_family == "springer_nature":
        return "springer_nature"
    if inspection.main_tex:
        return "custom_copy"
    return "generic"


def _write_managed_main(path: Path, content: str) -> None:
    marker = "% gw-mos scaffold"
    if path.exists():
        existing = read_text(path)
        if marker not in existing and "Scaffold draft." not in existing:
            raise ValueError(f"Refusing to overwrite user-managed draft file: {path}")
    write_text(path, content)


def _render_elsevier_main(spec: PaperSpec, section_specs: list[tuple[str, str, str]], inspection: TemplateInspection) -> str:
    journal_name = _latex_escape(spec.target_journal or spec.journal_family)
    title = _latex_escape(spec.title_working or "Working Title")
    abstract = _latex_escape(_abstract_placeholder(spec))
    keywords = " \\sep ".join(_latex_escape(term) for term in _keyword_terms(spec))
    body = "\n\n".join(_section_inputs(section_specs))
    return (
        "% gw-mos scaffold\n"
        f"% template origin: {inspection.selected_path or 'none'}\n"
        "\\documentclass[preprint,12pt]{elsarticle}\n"
        "\\usepackage{amssymb}\n"
        "\\usepackage{amsmath}\n"
        "\\usepackage{amsthm}\n\n"
        f"\\journal{{{journal_name}}}\n\n"
        "\\begin{document}\n\n"
        "\\begin{frontmatter}\n\n"
        f"\\title{{{title}}}\n"
        "\\author{}\n"
        "\\affiliation{organization={},addressline={},city={},postcode={},state={},country={}}\n\n"
        "\\begin{abstract}\n"
        f"{abstract}\n"
        "\\end{abstract}\n\n"
        "\\begin{keyword}\n"
        f"{keywords}\n"
        "\\end{keyword}\n\n"
        "\\end{frontmatter}\n\n"
        f"{body}\n\n"
        "\\bibliographystyle{elsarticle-num}\n"
        "\\bibliography{../02_literature/library}\n\n"
        "\\end{document}\n"
    )


def _render_springer_main(spec: PaperSpec, section_specs: list[tuple[str, str, str]], inspection: TemplateInspection) -> str:
    short_title = _latex_escape((spec.title_working or "Working Title")[:80])
    title = _latex_escape(spec.title_working or "Working Title")
    abstract = _latex_escape(_abstract_placeholder(spec))
    keywords = ", ".join(_latex_escape(term) for term in _keyword_terms(spec))
    body = "\n\n".join(_section_inputs(section_specs))
    return (
        "% gw-mos scaffold\n"
        f"% template origin: {inspection.selected_path or 'none'}\n"
        "\\documentclass[pdflatex,sn-mathphys-num]{sn-jnl}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{multirow}\n"
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        "\\usepackage{amsthm}\n"
        "\\usepackage{mathrsfs}\n"
        "\\usepackage[title]{appendix}\n"
        "\\usepackage{xcolor}\n"
        "\\usepackage{textcomp}\n"
        "\\usepackage{manyfoot}\n"
        "\\usepackage{booktabs}\n\n"
        "\\theoremstyle{thmstyleone}\n"
        "\\newtheorem{theorem}{Theorem}\n"
        "\\newtheorem{proposition}[theorem]{Proposition}\n"
        "\\theoremstyle{thmstyletwo}\n"
        "\\newtheorem{remark}{Remark}\n"
        "\\theoremstyle{thmstylethree}\n"
        "\\newtheorem{definition}{Definition}\n\n"
        "\\raggedbottom\n\n"
        "\\begin{document}\n\n"
        f"\\title[{short_title}]{{{title}}}\n"
        "\\author*[1]{\\fnm{First} \\sur{Author}}\\email{author@example.com}\n"
        "\\affil*[1]{\\orgdiv{Department}, \\orgname{Institution}, \\orgaddress{\\street{Street}, \\city{City}, \\postcode{00000}, \\state{State}, \\country{Country}}}\n\n"
        f"\\abstract{{{abstract}}}\n\n"
        f"\\keywords{{{keywords}}}\n\n"
        "\\maketitle\n\n"
        f"{body}\n\n"
        "\\bibliography{../02_literature/library}\n\n"
        "\\end{document}\n"
    )


def _render_generic_main(spec: PaperSpec, section_specs: list[tuple[str, str, str]], inspection: TemplateInspection) -> str:
    title = _latex_escape(spec.title_working or "Working Title")
    keywords = ", ".join(_latex_escape(term) for term in _keyword_terms(spec))
    body = "\n\n".join(_section_inputs(section_specs))
    return (
        "% gw-mos scaffold\n"
        f"% template origin: {inspection.selected_path or 'none'}\n"
        "\\documentclass[12pt]{article}\n"
        "\\usepackage{amsmath,amssymb,amsthm,graphicx,booktabs}\n\n"
        f"\\title{{{title}}}\n"
        "\\author{}\n"
        "\\date{}\n\n"
        "\\begin{document}\n"
        "\\maketitle\n\n"
        "\\begin{abstract}\n"
        f"{_latex_escape(_abstract_placeholder(spec))}\n"
        "\\end{abstract}\n\n"
        f"% Keywords: {keywords}\n\n"
        f"{body}\n\n"
        "\\bibliography{../02_literature/library}\n\n"
        "\\end{document}\n"
    )


def _patch_custom_main(
    main_tex_path: Path,
    spec: PaperSpec,
    section_specs: list[tuple[str, str, str]],
) -> None:
    content = read_text(main_tex_path)
    title = _latex_escape(spec.title_working or "Working Title")
    abstract = _latex_escape(_abstract_placeholder(spec))
    keywords = ", ".join(_latex_escape(term) for term in _keyword_terms(spec))
    replacements = {
        "\\title{\\bf Title}": f"\\title{{\\bf {title}}}",
        "\\title{}": f"\\title{{{title}}}",
        "\\title[Article Title]{Article Title}": f"\\title[{title}]{{{title}}}",
        "\\title{Title}": f"\\title{{{title}}}",
        "The text of your abstract. 200 or fewer words.": abstract,
        "Abstract text.": abstract,
        "3 to 6 keywords, that do not appear in the title": keywords,
        "Article Title": title,
    }
    for source, target in replacements.items():
        content = content.replace(source, target)
    content = _inject_custom_sections(content=content, section_specs=section_specs)
    if "% gw-mos scaffold" not in content:
        content = "% gw-mos scaffold\n" + content
    write_text(main_tex_path, content)


def _section_inputs(section_specs: list[tuple[str, str, str]]) -> list[str]:
    return [f"\\input{{sections/{slug}}}" for slug, _, _ in section_specs]


def _abstract_placeholder(spec: PaperSpec) -> str:
    problem = spec.problem_statement or "This paper develops the core research contribution."
    claim_summary = _claim_summary(spec)
    if claim_summary:
        return f"{problem} {claim_summary} This abstract is a scaffold and should be revised after proofs and experiments stabilize."
    return f"{problem} This abstract is a scaffold and should be revised after proofs and experiments stabilize."


def _keyword_terms(spec: PaperSpec) -> list[str]:
    tokens = [token.strip(",.") for token in (spec.title_working or "").split() if len(token) > 3]
    if not tokens:
        terms = ["theory", "methods"]
        if "experiment" in spec.contribution_type:
            terms.append("experiments")
        return terms
    keywords = tokens[:3]
    if "experiment" in spec.contribution_type and "experiments" not in {token.lower() for token in keywords}:
        keywords.append("experiments")
    return [token.lower() for token in keywords]


def _claim_summary(spec: PaperSpec) -> str:
    if not spec.core_claims:
        return ""
    first = spec.core_claims[0].text.rstrip(".")
    if len(spec.core_claims) == 1:
        return f"The current draft centers the manuscript around the claim that {first.lower()}."
    return f"The current draft emphasizes {len(spec.core_claims)} core claims, beginning with the statement that {first.lower()}."


def _introduction_body(spec: PaperSpec) -> str:
    lines = [
        spec.problem_statement or "State the problem, context, and motivation.",
        "",
        "% TODO: Add problem setup, contribution framing, and journal-specific motivation.",
    ]
    return "\n".join(lines)


def _related_work_body(spec: PaperSpec) -> str:
    return "\n".join(
        [
            "% TODO: Summarize nearest prior work from 02_literature/novelty_map.md.",
            "% TODO: Make novelty risks explicit and compare assumptions and evidence burden.",
        ]
    )


def _theory_body(spec: PaperSpec) -> str:
    lines = ["% TODO: Define notation, assumptions, lemmas, and main theorem statements."]
    if spec.core_claims:
        lines.append("% Current extracted claims:")
        lines.extend(f"% - [{claim.id}] {claim.text}" for claim in spec.core_claims)
    if spec.assumptions:
        lines.append("% Current extracted assumptions:")
        lines.extend(f"% - {assumption}" for assumption in spec.assumptions)
    return "\n".join(lines)


def _experiments_body(spec: PaperSpec) -> str:
    lines = ["% TODO: Map each experiment to a named theoretical claim and expected failure mode."]
    if spec.dataset_needs:
        lines.append("% Dataset needs:")
        lines.extend(f"% - {need}" for need in spec.dataset_needs)
    return "\n".join(lines)


def _discussion_body(spec: PaperSpec) -> str:
    return "\n".join(
        [
            "% TODO: Interpret the theory and experimental results together.",
            "% TODO: Document limitations, regime restrictions, and unresolved edge cases.",
        ]
    )


def _conclusion_body(spec: PaperSpec) -> str:
    return "\n".join(
        [
            "% TODO: Summarize the main contribution and immediate follow-up questions.",
            "% TODO: Re-check this section after final_write.",
        ]
    )


def _sections_readme(mode: str, spec: PaperSpec) -> str:
    lines = [
        "# Draft Sections",
        "",
        f"- Scaffold mode: `{mode}`",
        f"- Working title: `{spec.title_working or 'Working Title'}`",
        "",
        "The `.tex` files in this directory are generated scaffold sections.",
    ]
    if mode == "custom_copy":
        lines.append("The current `main.tex` preserves the custom template preamble and end matter while routing the body through `\\input{sections/...}`.")
    else:
        lines.append("The generated `main.tex` uses `\\input{sections/...}` to include these files during local drafting.")
    lines.append("")
    lines.append("For submission, a later build step can flatten these sections back into a single journal-conforming file if needed.")
    return "\n".join(lines) + "\n"


def _latex_escape(text: str) -> str:
    replacements = {
        "\\": "\\textbackslash{}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
    }
    escaped = []
    for char in text:
        escaped.append(replacements.get(char, char))
    return "".join(escaped)


def _inject_custom_sections(content: str, section_specs: list[tuple[str, str, str]]) -> str:
    section_block = _managed_section_block(section_specs)
    if MANAGED_SECTION_BEGIN in content and MANAGED_SECTION_END in content:
        pattern = re.compile(
            rf"{re.escape(MANAGED_SECTION_BEGIN)}.*?{re.escape(MANAGED_SECTION_END)}",
            re.DOTALL,
        )
        return pattern.sub(section_block, content, count=1)

    body_end = _find_body_end(content)
    body_start = _find_body_start(content)
    if body_start is None or body_end is None or body_start >= body_end:
        insertion_point = body_end if body_end is not None else len(content)
        return content[:insertion_point] + "\n\n" + section_block + "\n\n" + content[insertion_point:]

    prefix = content[:body_start].rstrip()
    suffix = content[body_end:].lstrip()
    return prefix + "\n\n" + section_block + "\n\n" + suffix


def _managed_section_block(section_specs: list[tuple[str, str, str]]) -> str:
    lines = [MANAGED_SECTION_BEGIN]
    lines.extend(_section_inputs(section_specs))
    lines.append(MANAGED_SECTION_END)
    return "\n".join(lines)


def _find_body_start(content: str) -> int | None:
    section_match = re.search(r"\\section\*?\{", content)
    if section_match:
        return section_match.start()

    for token in (r"\maketitle", r"\end{abstract}", r"\begin{document}"):
        match = re.search(re.escape(token), content)
        if match:
            line_end = content.find("\n", match.end())
            if line_end == -1:
                return match.end()
            return line_end + 1
    return None


def _find_body_end(content: str) -> int | None:
    for token in (r"\bibliography{", r"\begin{thebibliography}", r"\printbibliography", r"\end{document}"):
        match = re.search(re.escape(token), content)
        if match:
            return match.start()
    return None
