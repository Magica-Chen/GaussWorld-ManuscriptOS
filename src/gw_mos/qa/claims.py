from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import yaml

from gw_mos.artifacts.models import CitationRecord, ClaimClassification, PaperSpec
from gw_mos.artifacts.readers import read_json
from gw_mos.artifacts.writers import write_text
from gw_mos.theory.theorem_ledger import LedgerEntry, build_theorem_ledger


@dataclass(frozen=True)
class ClaimEvidenceRow:
    claim_id: str
    claim_text: str
    classification: ClaimClassification
    evidence_type: str
    evidence_ref: str
    status: str


def write_claim_evidence_matrix(project_root: Path) -> list[ClaimEvidenceRow]:
    spec = _load_spec(project_root)
    ledger = build_theorem_ledger(spec)
    citations = _load_citations(project_root)
    results = read_json(project_root / "04_experiments/results_registry.json")
    rows = build_claim_evidence_rows(spec=spec, entries=ledger["entries"], citations=citations, results_registry=results)
    matrix_path = project_root / "06_qa/claim_evidence_matrix.csv"
    _write_csv(matrix_path, rows)
    write_text(project_root / "06_qa/alignment_review.md", render_alignment_review(rows))
    return rows


def build_claim_evidence_rows(
    *,
    spec: PaperSpec,
    entries: list[LedgerEntry],
    citations: list[CitationRecord],
    results_registry: dict,
) -> list[ClaimEvidenceRow]:
    runs_by_claim: dict[str, list[dict]] = {}
    for run in results_registry.get("runs", []):
        for claim_id in run.get("claim_ids", []):
            runs_by_claim.setdefault(claim_id, []).append(run)

    citation_ref = citations[0].bibtex_key or citations[0].id if citations else ""
    rows: list[ClaimEvidenceRow] = []
    for claim in spec.core_claims:
        entry = next((item for item in entries if item.claim_id == claim.id), None)
        runs = runs_by_claim.get(claim.id, [])
        if entry and entry.evidence_mode == "proof":
            if entry.proof_status == "complete":
                rows.append(
                    ClaimEvidenceRow(
                        claim_id=claim.id,
                        claim_text=claim.text,
                        classification=ClaimClassification.proved,
                        evidence_type="theorem",
                        evidence_ref=entry.label,
                        status="pass",
                    )
                )
            else:
                rows.append(
                    ClaimEvidenceRow(
                        claim_id=claim.id,
                        claim_text=claim.text,
                        classification=ClaimClassification.conjectural,
                        evidence_type="theorem",
                        evidence_ref=entry.label,
                        status="needs_proof" if entry.proof_status == "missing" else "partial",
                    )
                )
            continue

        completed_run = next((run for run in runs if run.get("status") in {"completed", "passed"}), None)
        if completed_run is not None:
            rows.append(
                ClaimEvidenceRow(
                    claim_id=claim.id,
                    claim_text=claim.text,
                    classification=ClaimClassification.experimentally_supported,
                    evidence_type="experiment",
                    evidence_ref=completed_run.get("run_id", ""),
                    status="pass",
                )
            )
            continue

        if runs:
            rows.append(
                ClaimEvidenceRow(
                    claim_id=claim.id,
                    claim_text=claim.text,
                    classification=ClaimClassification.conjectural,
                    evidence_type="experiment",
                    evidence_ref=runs[0].get("run_id", ""),
                    status="planned",
                )
            )
            continue

        if citation_ref:
            rows.append(
                ClaimEvidenceRow(
                    claim_id=claim.id,
                    claim_text=claim.text,
                    classification=ClaimClassification.cited,
                    evidence_type="citation",
                    evidence_ref=citation_ref,
                    status="pass",
                )
            )
            continue

        rows.append(
            ClaimEvidenceRow(
                claim_id=claim.id,
                claim_text=claim.text,
                classification=ClaimClassification.editorial,
                evidence_type="editorial",
                evidence_ref="",
                status="missing_evidence",
            )
        )
    return rows


def render_alignment_review(rows: list[ClaimEvidenceRow]) -> str:
    lines = [
        "# Alignment Review",
        "",
        "## Summary",
        f"- Total claims audited: `{len(rows)}`",
        f"- Missing or incomplete claims: `{sum(1 for row in rows if row.status not in {'pass'})}`",
        "",
        "## Findings",
    ]
    if not rows:
        lines.append("- No claims were available for alignment review.")
    for row in rows:
        lines.append(
            f"- `{row.claim_id}` -> classification=`{row.classification.value}`, evidence=`{row.evidence_type}`, ref=`{row.evidence_ref or 'none'}`, status=`{row.status}`"
        )
    return "\n".join(lines) + "\n"


def claim_audit_summary(project_root: Path) -> dict[str, int]:
    matrix_path = project_root / "06_qa/claim_evidence_matrix.csv"
    if not matrix_path.exists():
        return {"missing": 0, "pass": 0}
    rows = list(csv.DictReader(matrix_path.read_text(encoding="utf-8").splitlines()))
    return {
        "missing": sum(1 for row in rows if row.get("status") not in {"pass"}),
        "pass": sum(1 for row in rows if row.get("status") == "pass"),
    }


def _write_csv(path: Path, rows: list[ClaimEvidenceRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["claim_id", "claim_text", "classification", "evidence_type", "evidence_ref", "status"])
        for row in rows:
            writer.writerow(
                [
                    row.claim_id,
                    row.claim_text,
                    row.classification.value,
                    row.evidence_type,
                    row.evidence_ref,
                    row.status,
                ]
            )


def _load_spec(project_root: Path) -> PaperSpec:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    return PaperSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))


def _load_citations(project_root: Path) -> list[CitationRecord]:
    payload = read_json(project_root / "02_literature/citation_index.json")
    return [CitationRecord.model_validate(item) for item in payload.get("papers", [])]
