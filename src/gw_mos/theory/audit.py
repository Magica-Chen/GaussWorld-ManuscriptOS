from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from gw_mos.artifacts.models import PaperSpec
from gw_mos.artifacts.readers import read_text
from gw_mos.artifacts.writers import write_text
from gw_mos.prompt_loader import load_prompt
from gw_mos.providers.base import ProviderError, ProviderRequest
from gw_mos.providers.registry import build_provider, provider_available
from gw_mos.theory.assumptions import missing_assumption_topics
from gw_mos.theory.theorem_ledger import LedgerEntry, build_theorem_ledger

SCOPE_RISK_TOKENS = ("all", "always", "arbitrary", "any", "uniformly", "without loss", "global")


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    title: str
    detail: str


def generate_proof_audit(project_root: Path) -> list[AuditFinding]:
    spec = _load_spec(project_root)
    ledger = build_theorem_ledger(spec)["entries"]
    notation_text = read_text(project_root / "03_theory/notation.md")
    findings = deterministic_proof_audit(spec=spec, ledger=ledger, notation_text=notation_text)
    critique = _provider_critique(spec=spec, ledger=ledger, start=project_root)
    write_text(project_root / "03_theory/proof_audit.md", render_proof_audit(spec, findings, critique))
    _write_disputes(project_root, findings)
    return findings


def deterministic_proof_audit(spec: PaperSpec, ledger: list[LedgerEntry], notation_text: str) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    missing_topics = missing_assumption_topics(spec)
    if missing_topics:
        findings.append(
            AuditFinding(
                severity="high",
                title="Assumption coverage gaps",
                detail=f"The current assumptions do not explicitly address: {', '.join(missing_topics)}.",
            )
        )

    for entry in ledger:
        if entry.kind == "theorem" and entry.proof_status == "missing":
            findings.append(
                AuditFinding(
                    severity="high",
                    title=f"{entry.label} has no completed proof",
                    detail="The theorem ledger still marks this result as missing, so manuscript language should remain conjectural or roadmap-only.",
                )
            )
        if entry.kind == "theorem" and not entry.dependencies:
            findings.append(
                AuditFinding(
                    severity="medium",
                    title=f"{entry.label} has no explicit dependencies",
                    detail="Add definitions or lemma dependencies so the proof order is explicit rather than implied.",
                )
            )
        if any(token in entry.statement.lower() for token in SCOPE_RISK_TOKENS):
            findings.append(
                AuditFinding(
                    severity="medium",
                    title=f"{entry.label} may overstate its scope",
                    detail=f"The statement contains global-scope language (`{_matched_scope_token(entry.statement)}`) that often needs tighter assumptions or a local regime.",
                )
            )
        if entry.kind == "empirical" and not entry.dependencies:
            findings.append(
                AuditFinding(
                    severity="medium",
                    title=f"{entry.label} is disconnected from the theorem program",
                    detail="Link the empirical claim to a theorem, lemma, or explicitly mark it as illustrative only.",
                )
            )

    if "No notation diagnostics yet." in notation_text:
        findings.append(
            AuditFinding(
                severity="low",
                title="Notation audit remains shallow",
                detail="The notation file does not yet expose concrete conflicts, so symbol consistency still needs a manual pass.",
            )
        )
    if not findings:
        findings.append(
            AuditFinding(
                severity="low",
                title="No deterministic proof blockers detected",
                detail="The current audit did not find obvious structural issues, but this is still not a formal proof check.",
            )
        )
    return findings


def render_proof_audit(spec: PaperSpec, findings: list[AuditFinding], critique: str) -> str:
    lines = [
        "# Proof Audit",
        "",
        f"- Working title: `{spec.title_working or 'Untitled'}`",
        f"- Contribution modes: `{', '.join(spec.contribution_type) or 'unspecified'}`",
        f"- Findings: `{len(findings)}`",
        "",
        "## Findings",
    ]
    for finding in findings:
        lines.extend(
            [
                f"### {finding.severity.upper()}: {finding.title}",
                finding.detail,
                "",
            ]
        )
    if critique:
        lines.extend(["## Anthropic Critique", critique.strip(), ""])
    lines.extend(
        [
            "## Next Actions",
            "- Tighten theorem scope before promoting missing proofs to definitive claims.",
            "- Ensure experiments target only theorem regimes that are explicitly justified in the assumptions.",
            "- Resolve high-severity findings before journal-style polishing.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _provider_critique(spec: PaperSpec, ledger: list[LedgerEntry], start: Path) -> str:
    if not provider_available("anthropic", start=start):
        return ""
    provider = build_provider("anthropic", start=start)
    prompt = (
        "Audit this theorem program for hidden assumptions, scope overclaims, and likely counterexample regimes. "
        "Return 3-6 concise bullets.\n\n"
        f"Problem: {spec.problem_statement}\n"
        + "\n".join(f"- {entry.label}: {entry.statement}" for entry in ledger[:6])
    )
    try:
        response = provider.generate(
            ProviderRequest(
                prompt=prompt,
                system_prompt=load_prompt(
                    "agents/proof_auditor.md",
                    fallback="You are a skeptical mathematical reviewer. Focus on correctness risks, not style.",
                ),
                max_output_tokens=500,
            )
        )
    except ProviderError:
        return ""
    return response.content


def _write_disputes(project_root: Path, findings: list[AuditFinding]) -> None:
    dispute_root = project_root / "disputes"
    dispute_root.mkdir(parents=True, exist_ok=True)
    for index, finding in enumerate([item for item in findings if item.severity == "high"], start=1):
        path = dispute_root / f"proof_scope_dispute_{index:02d}.md"
        content = "\n".join(
            [
                f"# {finding.title}",
                "",
                "## Risk",
                finding.detail,
                "",
                "## Controller Decision",
                "Keep the claim marked as unproved or partially proved until the theorem statement and assumptions are tightened.",
                "",
            ]
        )
        write_text(path, content)


def _matched_scope_token(statement: str) -> str:
    lowered = statement.lower()
    for token in SCOPE_RISK_TOKENS:
        if token in lowered:
            return token
    return "broad scope"


def _load_spec(project_root: Path) -> PaperSpec:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    return PaperSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))
