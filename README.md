# GaussWorld-ManuscriptOS

`gw-mos` is a terminal-native research paper completion tool for theory-led work in mathematics, statistics, physics, and theory-heavy computational social science. The user-facing product is an interactive shell driven by natural-language requests; the stage machine and artefacts remain backend infrastructure behind that workflow.

## Current state

This repo currently supports:

- bare `gw-mos` interactive shell as the default entrypoint
- `/ready`, `/qa`, `/bundle`, `/artifacts`, and `/show` inside the shell
- project/workspace creation
- persisted state and runtime status files
- OpenAI/Anthropic profile storage with repo-local auth state and environment fallback
- OpenAI-backed planning hook for ambiguous NL requests, with Anthropic review when configured
- markdown-based prompt specs for the first provider-facing agents
- real `spec` stage generation from `idea.md`
- local literature ingestion for `.bib` files and PDFs
- grounded `library.bib`, `citation_index.json`, and `novelty_map.md` generation
- real `theory_program` stage generation for theorem ledger, assumptions, notation, and counterexample prompts
- real `experiment_design` stage generation for `experiment_plan.md`, `results_registry.json`, and per-run instruction markdown
- real `experiment_run` stage execution that materializes runnable scripts on demand and launches jobs in `tmux`
- real `alignment_review` stage generation for `claim_evidence_matrix.csv`
- real `final_write` stage generation for LaTeX section synthesis from current artefacts
- journal/template inspection and `journal_fit` stage output
- natural-language routing through `gw-mos run` and `gw-mos chat`
- template-backed draft scaffolding and end-to-end LaTeX build/QA
- submission-readiness verdicts in `06_qa/submission_readiness.md`
- submission bundles under `07_submission/` with manuscript source, PDF, and reports
- tmux-backed experiment launching, status, logs, and stop commands
- on-demand experiment script materialization from instruction markdown during `exp start`

The main remaining hardening gaps are stronger novelty adjudication, richer experiment-result interpretation, and deeper journal-style refinement after evidence stabilizes.

## Development install

```bash
python -m pip install -e '.[dev]'
```

## CLI

```bash
gw-mos
gw-mos --help
gw-mos init demo-paper --journal custom
gw-mos ready demo-paper
gw-mos status demo-paper
gw-mos stage run spec demo-paper
gw-mos literature ingest demo-paper --bib refs.bib
gw-mos stage run theory_program demo-paper
gw-mos stage run experiment_design demo-paper
gw-mos stage run alignment_review demo-paper
gw-mos stage run final_write demo-paper
gw-mos run "build the pdf" --project demo-paper
gw-mos qa readiness demo-paper
gw-mos qa bundle demo-paper
gw-mos chat --project demo-paper
gw-mos auth add anthropic --profile reviewer --api-key ...
gw-mos exp start demo-paper
gw-mos exp status demo-paper
```

## Product direction

The target product is a terminal-native paper-completion tool:

- open a terminal
- write natural-language requests
- inspect outputs as the system updates artefacts
- end with `.tex` + PDF outputs, a readiness verdict, and a submission bundle

See [docs/product-target.md](/home/zodiac/GaussWorld-ManuscriptOS/docs/product-target.md).

## Design principles

- Artefacts over chat logs
- One controller, constrained agents
- Explicit stage gates and stop criteria
- Grounded citations and evidence tracking
- Continuous LaTeX and QA checks

See [docs/architecture.md](/home/zodiac/GaussWorld-ManuscriptOS/docs/architecture.md) and [docs/artifact-specs.md](/home/zodiac/GaussWorld-ManuscriptOS/docs/artifact-specs.md).
