# Architecture

`gw-mos` is structured around a persisted workflow controller:

1. `intake`
2. `spec`
3. `novelty`
4. `journal_fit`
5. `theory_program`
6. `experiment_design`
7. `scaffold_draft`
8. `experiment_run`
9. `alignment_review`
10. `final_write`
11. `build_qa`

Each stage consumes explicit files and produces explicit files. Agents are role-constrained workers; the controller remains authoritative for stage transitions and acceptance decisions.

## Key subsystems

- `artifacts/`: workspace layout and structured models
- `controller/`: stage machine, state persistence, gates
- `providers/` and `auth/`: OpenAI drafter and Anthropic reviewer wiring
- `journals/`: family packs and custom-template adapters
- `literature/`, `theory/`, `experiments/`, `writing/`, `qa/`: domain workflows
