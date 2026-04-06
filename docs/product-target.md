# Product Target

`gw-mos` is not just a stage runner. The intended product is a terminal-native paper-completion tool.

## Target UX

The user should be able to:

1. open a terminal
2. write a natural-language request
3. inspect what the tool did
4. iterate conversationally
5. end with a `.tex` manuscript and compiled PDF that are close to submission-ready

## Architecture Consequence

The current stage pipeline remains important, but it is backend infrastructure. The user-facing interface should increasingly center on:

- `gw-mos run "<natural language request>"`
- `gw-mos chat`

These interfaces should route requests into the existing artefact-driven controller rather than bypassing it.

## Near-Term Priority

The current high-value completed pieces are:

- deterministic natural-language routing over existing stages
- provider-backed planning fallback in the same NL interface
- experiment design, execution scaffolding, and claim-evidence auditing
- end-to-end PDF build from the NL workflow
- submission-readiness verdicts and `07_submission/` bundle generation
- interactive shell commands for readiness, QA, and bundle inspection

The next gaps are:

- stronger novelty adjudication and similarity scoring over public search hits
- richer experiment-result interpretation tied to actual outputs
- stronger journal-style refinement after evidence stabilizes
- deeper multi-agent orchestration beyond plan assistance
