from __future__ import annotations

from dataclasses import dataclass

from gw_mos.artifacts.models import ClaimRecord, PaperSpec

THEORY_HINTS = (
    "prove",
    "theorem",
    "lemma",
    "corollary",
    "proposition",
    "convergence",
    "consistency",
    "identifiability",
    "optimal",
    "bound",
    "stability",
)
EXPERIMENT_HINTS = (
    "experiment",
    "synthetic",
    "simulation",
    "dataset",
    "empirical",
    "demonstration",
    "real data",
)


@dataclass(frozen=True)
class LedgerEntry:
    claim_id: str
    label: str
    kind: str
    statement: str
    proof_status: str
    dependencies: list[str]
    evidence_mode: str


def build_theorem_ledger(spec: PaperSpec) -> dict[str, list[LedgerEntry] | list[str]]:
    entries: list[LedgerEntry] = []
    dependency_labels: list[str] = []
    theorem_count = 0
    experiment_count = 0

    for claim in spec.core_claims:
        kind = infer_claim_kind(claim)
        if kind == "theorem":
            theorem_count += 1
            label = f"Theorem {theorem_count}"
            dependencies = ["Definition 1"]
            if theorem_count > 1:
                dependencies.append(f"Theorem {theorem_count - 1}")
            proof_status = "missing"
            evidence_mode = "proof"
        elif kind == "empirical":
            experiment_count += 1
            label = f"Validation Claim {experiment_count}"
            dependencies = [entry.label for entry in entries if entry.kind == "theorem"][:2]
            proof_status = "not_applicable"
            evidence_mode = "experiment"
        else:
            label = f"Claim {claim.id}"
            dependencies = []
            proof_status = "partial"
            evidence_mode = "analysis"

        entry = LedgerEntry(
            claim_id=claim.id,
            label=label,
            kind=kind,
            statement=claim.text,
            proof_status=proof_status,
            dependencies=dependencies,
            evidence_mode=evidence_mode,
        )
        entries.append(entry)
        dependency_labels.extend(dependencies)

    if not entries:
        entries.append(
            LedgerEntry(
                claim_id="C1",
                label="Theorem 1",
                kind="theorem",
                statement=spec.problem_statement or "Main technical claim to be specified.",
                proof_status="missing",
                dependencies=["Definition 1"],
                evidence_mode="proof",
            )
        )

    unique_dependencies = []
    seen = set()
    for label in dependency_labels:
        if label not in seen:
            seen.add(label)
            unique_dependencies.append(label)

    return {
        "entries": entries,
        "dependencies": unique_dependencies,
    }


def infer_claim_kind(claim: ClaimRecord) -> str:
    lowered = claim.text.lower()
    if any(token in lowered for token in THEORY_HINTS):
        return "theorem"
    if any(token in lowered for token in EXPERIMENT_HINTS):
        return "empirical"
    return "analysis"
