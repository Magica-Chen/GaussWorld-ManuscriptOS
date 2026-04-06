from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from gw_mos.utils.subprocess import run_command
from gw_mos.writing.latex import latex_build_plan

ERROR_RE = re.compile(r"^! (.+)$", re.MULTILINE)
WARNING_RE = re.compile(r"^(?:LaTeX|Package .*?) Warning: (.+)$", re.MULTILINE)


class BuildCommandResult(BaseModel):
    command: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CompileResult(BaseModel):
    success: bool
    engine: str
    main_tex: str
    pdf_path: str | None = None
    log_path: str
    report_path: str
    ran_at: str
    missing_tools: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    commands: list[BuildCommandResult] = Field(default_factory=list)


def compile_project(project_root: Path) -> CompileResult:
    draft_root = project_root / "05_draft"
    qa_root = project_root / "06_qa"
    main_tex = draft_root / "main.tex"
    log_path = qa_root / "compile_log.txt"
    report_path = qa_root / "qa_report.md"
    ran_at = _utc_now()

    if not main_tex.exists():
        result = CompileResult(
            success=False,
            engine="none",
            main_tex=str(main_tex),
            log_path=str(log_path),
            report_path=str(report_path),
            ran_at=ran_at,
            errors=[f"Missing main TeX file: {main_tex}"],
        )
        _write_compile_log(log_path, result)
        return result

    plan = latex_build_plan(main_tex)
    if plan.missing_tools:
        result = CompileResult(
            success=False,
            engine=plan.engine,
            main_tex=str(main_tex),
            log_path=str(log_path),
            report_path=str(report_path),
            ran_at=ran_at,
            missing_tools=plan.missing_tools,
            errors=[f"Missing required TeX tool(s): {', '.join(plan.missing_tools)}"],
        )
        _write_compile_log(log_path, result)
        return result

    command_results: list[BuildCommandResult] = []
    build_env = _build_tex_env(draft_root)
    for command in plan.commands:
        completed = run_command(command, cwd=draft_root, env=build_env)
        command_results.append(
            BuildCommandResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        )
        if completed.returncode != 0:
            break

    raw_log = _collect_raw_log(draft_root=draft_root, command_results=command_results)
    errors = _collect_errors(raw_log)
    warnings = _collect_warnings(raw_log)
    pdf_path = draft_root / "main.pdf"
    success = all(item.returncode == 0 for item in command_results) and pdf_path.exists()
    if not success and not errors:
        errors.append("Compilation failed without an extracted LaTeX error. Inspect compile_log.txt.")

    result = CompileResult(
        success=success,
        engine=plan.engine,
        main_tex=str(main_tex),
        pdf_path=str(pdf_path) if pdf_path.exists() else None,
        log_path=str(log_path),
        report_path=str(report_path),
        ran_at=ran_at,
        missing_tools=plan.missing_tools,
        errors=errors,
        warnings=warnings,
        commands=command_results,
    )
    _write_compile_log(log_path, result, raw_log=raw_log)
    return result


def _collect_raw_log(draft_root: Path, command_results: list[BuildCommandResult]) -> str:
    parts = [f"cwd: {draft_root}"]
    for item in command_results:
        parts.append("")
        parts.append(f"$ {' '.join(item.command)}")
        parts.append(f"returncode: {item.returncode}")
        if item.stdout:
            parts.append("--- stdout ---")
            parts.append(item.stdout.rstrip())
        if item.stderr:
            parts.append("--- stderr ---")
            parts.append(item.stderr.rstrip())
    latex_log = draft_root / "main.log"
    if latex_log.exists():
        parts.append("")
        parts.append("--- main.log ---")
        parts.append(latex_log.read_text(encoding="utf-8", errors="replace").rstrip())
    return "\n".join(parts).strip() + "\n"


def _collect_errors(text: str) -> list[str]:
    extracted = [match.strip() for match in ERROR_RE.findall(text)]
    if "Undefined control sequence." in text and "Undefined control sequence." not in extracted:
        extracted.append("Undefined control sequence.")
    if "Emergency stop." in text and "Emergency stop." not in extracted:
        extracted.append("Emergency stop.")
    return _dedupe(extracted)


def _collect_warnings(text: str) -> list[str]:
    extracted = [match.strip() for match in WARNING_RE.findall(text)]
    for needle in (
        "There were undefined references.",
        "Citation",
        "Reference",
        "Label(s) may have changed.",
    ):
        if needle in text:
            extracted.append(needle)
    return _dedupe(extracted)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered[:10]


def _write_compile_log(path: Path, result: CompileResult, raw_log: str | None = None) -> None:
    lines = [
        f"ran_at: {result.ran_at}",
        f"engine: {result.engine}",
        f"success: {result.success}",
        f"main_tex: {result.main_tex}",
        f"pdf_path: {result.pdf_path or 'not produced'}",
    ]
    if result.missing_tools:
        lines.append(f"missing_tools: {', '.join(result.missing_tools)}")
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    if raw_log:
        lines.extend(["", raw_log.rstrip()])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_tex_env(draft_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    bst_dir = draft_root / "bst"
    if bst_dir.exists():
        existing = env.get("BSTINPUTS", "")
        env["BSTINPUTS"] = f"{bst_dir}:{existing}" if existing else str(bst_dir)
    return env


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
