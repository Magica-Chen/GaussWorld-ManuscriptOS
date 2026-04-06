from __future__ import annotations

from gw_mos.agents.base import AgentContract


CONTRACTS: dict[str, AgentContract] = {
    "build_agent": AgentContract(
        name="build_agent",
        reads=["05_draft/main.tex"],
        writes=["06_qa/qa_report.md", "06_qa/compile_log.txt"],
        exit_criteria=["Build and QA report written"],
    ),
    "claim_evidence_agent": AgentContract(
        name="claim_evidence_agent",
        reads=["01_spec/paper_spec.yaml", "02_literature/citation_index.json", "04_experiments/results_registry.json"],
        writes=["06_qa/claim_evidence_matrix.csv"],
        exit_criteria=["Each major claim classified and linked to evidence"],
    ),
    "experiment_designer_agent": AgentContract(
        name="experiment_designer_agent",
        reads=["03_theory/theorem_ledger.md", "03_theory/proof_audit.md"],
        writes=["04_experiments/experiment_plan.md", "04_experiments/jobs/"],
        exit_criteria=["Experiments mapped to claims and instruction files emitted"],
    ),
    "journal_fit_agent": AgentContract(
        name="journal_fit_agent",
        reads=["01_spec/paper_spec.yaml", "00_intake/journal_targets.md"],
        writes=["01_spec/journal_fit.md"],
        exit_criteria=["Journal fit rubric completed"],
    ),
    "literature_agent": AgentContract(
        name="literature_agent",
        reads=["01_spec/paper_spec.yaml"],
        writes=["02_literature/novelty_map.md", "02_literature/library.bib", "02_literature/citation_index.json"],
        exit_criteria=["Closest papers listed", "Novelty risks recorded", "BibTeX grounded"],
    ),
    "proof_auditor_agent": AgentContract(
        name="proof_auditor_agent",
        reads=["03_theory/theorem_ledger.md", "03_theory/assumptions.md"],
        writes=["03_theory/proof_audit.md", "03_theory/counterexamples.md", "disputes/"],
        exit_criteria=["Weak assumptions and counterexamples recorded"],
    ),
    "results_auditor_agent": AgentContract(
        name="results_auditor_agent",
        reads=["04_experiments/results_registry.json", "04_experiments/jobs/"],
        writes=["04_experiments/results_audit.md", "06_qa/qa_report.md"],
        exit_criteria=["Run outputs reviewed against claims"],
    ),
    "spec_agent": AgentContract(
        name="spec_agent",
        reads=["00_intake/idea.md", "00_intake/constraints.md"],
        writes=["01_spec/paper_spec.yaml", "01_spec/contribution_hypotheses.md"],
        exit_criteria=["Problem statement normalized", "Claims and assumptions captured"],
    ),
    "theory_architect_agent": AgentContract(
        name="theory_architect_agent",
        reads=["01_spec/paper_spec.yaml"],
        writes=["03_theory/theorem_ledger.md", "03_theory/assumptions.md", "03_theory/notation.md"],
        exit_criteria=["Theorem graph drafted", "Assumptions declared"],
    ),
    "writing_agent": AgentContract(
        name="writing_agent",
        reads=["01_spec/paper_spec.yaml", "02_literature/novelty_map.md", "03_theory/theorem_ledger.md", "04_experiments/experiment_plan.md"],
        writes=["05_draft/main.tex", "05_draft/sections/"],
        exit_criteria=["Draft files updated consistently with evidence"],
    ),
}


def get_contract(name: str) -> AgentContract:
    return CONTRACTS[name]
