from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gw_mos.artifacts.readers import read_json
from gw_mos.artifacts.writers import write_text


@dataclass(frozen=True)
class ExperimentAuditRow:
    run_id: str
    status: str
    claim_ids: list[str]
    note: str


def write_results_audit(project_root: Path) -> list[ExperimentAuditRow]:
    registry = read_json(project_root / "04_experiments/results_registry.json")
    rows = build_results_audit(project_root, registry)
    write_text(project_root / "04_experiments/results_audit.md", render_results_audit(rows))
    return rows


def build_results_audit(project_root: Path, registry: dict) -> list[ExperimentAuditRow]:
    rows: list[ExperimentAuditRow] = []
    for run_record in registry.get("runs", []):
        run_id = run_record.get("run_id", "")
        status = run_record.get("status", "unknown")
        log_path = project_root / f"04_experiments/outputs/{run_id}.log"
        note = _status_note(status=status, log_path=log_path)
        rows.append(
            ExperimentAuditRow(
                run_id=run_id,
                status=status,
                claim_ids=list(run_record.get("claim_ids", [])),
                note=note,
            )
        )
    return rows


def render_results_audit(rows: list[ExperimentAuditRow]) -> str:
    lines = [
        "# Results Audit",
        "",
        f"- Runs tracked: `{len(rows)}`",
        "",
        "## Findings",
    ]
    if not rows:
        lines.append("- No experiment runs are registered yet.")
    for row in rows:
        lines.append(
            f"- `{row.run_id}` -> status=`{row.status}`, claims=`{', '.join(row.claim_ids) or 'none'}`. {row.note}"
        )
    lines.extend(
        [
            "",
            "## Next Actions",
            "- Replace stub scripts before treating failed runs as scientific evidence.",
            "- Promote planned runs to completed only after the generating script, outputs, and qualitative takeaway are recorded.",
        ]
    )
    return "\n".join(lines) + "\n"


def _status_note(status: str, log_path: Path) -> str:
    if status == "completed":
        return "The run completed; inspect outputs and map the result back to the intended theoretical claim."
    if status == "running":
        return "The run is still active in tmux."
    if status == "planned":
        return "The run has not been launched yet."
    if status == "awaiting_generation":
        return "The run could not be materialized from its instruction file; configure a provider or inspect the generated fallback script."
    if status == "stopped":
        return "The run was manually stopped and should not be cited as evidence."
    if status == "failed":
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8", errors="replace")
            if "could not materialize a real script" in content.lower():
                return "The run used the fallback materialization script because no provider-generated execution plan was available."
        return "The run failed; inspect the log and decide whether the issue is implementation, data, or theory mismatch."
    return "No audit note is available yet."
