# Agent Contracts

Every agent should declare:

- inputs it reads
- outputs it owns
- exit criteria
- escalation conditions

## Initial agent set

- `spec_agent`: normalize `idea.md` into `paper_spec.yaml`
- `literature_agent`: produce grounded references and novelty risks
- `journal_fit_agent`: assess fit, template, and section norms
- `theory_architect_agent`: formalize notation, assumptions, theorem graph
- `proof_auditor_agent`: search for missing assumptions and counterexamples
- `experiment_designer_agent`: map experiments to claims
- `results_auditor_agent`: decide whether outputs support named claims
- `claim_evidence_agent`: keep the evidence matrix complete
- `writing_agent`: synthesize manuscript text from approved artefacts
- `build_agent`: compile LaTeX and emit QA reports
