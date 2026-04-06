from __future__ import annotations

from dataclasses import dataclass

from gw_mos.controller.stages import Stage


@dataclass(frozen=True)
class StageGate:
    required_inputs: tuple[str, ...]
    owned_outputs: tuple[str, ...]


STAGE_GATES: dict[Stage, StageGate] = {
    Stage.intake: StageGate(("00_intake/idea.md",), ("runtime/state.json",)),
    Stage.spec: StageGate(("00_intake/idea.md",), ("01_spec/paper_spec.yaml",)),
    Stage.novelty: StageGate(("01_spec/paper_spec.yaml",), ("02_literature/novelty_map.md", "02_literature/library.bib")),
    Stage.journal_fit: StageGate(("01_spec/paper_spec.yaml",), ("01_spec/journal_fit.md",)),
    Stage.theory_program: StageGate(("01_spec/paper_spec.yaml",), ("03_theory/theorem_ledger.md",)),
    Stage.proof_audit: StageGate(("03_theory/theorem_ledger.md", "03_theory/assumptions.md"), ("03_theory/proof_audit.md",)),
    Stage.experiment_design: StageGate(("03_theory/proof_audit.md",), ("04_experiments/experiment_plan.md",)),
    Stage.scaffold_draft: StageGate(("01_spec/paper_spec.yaml",), ("05_draft/main.tex",)),
    Stage.experiment_run: StageGate(("04_experiments/experiment_plan.md",), ("04_experiments/results_registry.json", "04_experiments/results_audit.md")),
    Stage.alignment_review: StageGate(("04_experiments/results_registry.json",), ("06_qa/claim_evidence_matrix.csv",)),
    Stage.final_write: StageGate(("06_qa/claim_evidence_matrix.csv",), ("05_draft/sections/introduction.tex",)),
    Stage.build_qa: StageGate(("05_draft/main.tex",), ("06_qa/qa_report.md",)),
}
