from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from gw_mos.agent_runtime import complete_with_openai
from gw_mos.artifacts.models import ExperimentRunRecord, PaperSpec
from gw_mos.artifacts.writers import write_json, write_text
from gw_mos.theory.theorem_ledger import LedgerEntry, build_theorem_ledger


@dataclass(frozen=True)
class PlannedExperiment:
    experiment_id: str
    title: str
    category: str
    claim_id: str
    target_label: str
    objective: str
    design: str
    failure_meaning: str
    data_need: str
    priority: str


def generate_experiment_plan(project_root: Path) -> list[PlannedExperiment]:
    spec = _load_spec(project_root)
    ledger = build_theorem_ledger(spec)
    planned = plan_experiments(spec=spec, entries=ledger["entries"])
    _write_instruction_files(project_root, planned)
    write_text(project_root / "04_experiments/experiment_plan.md", render_experiment_plan(spec, planned))
    write_json(project_root / "04_experiments/results_registry.json", render_results_registry(project_root, planned))
    return planned


def plan_experiments(spec: PaperSpec, entries: list[LedgerEntry]) -> list[PlannedExperiment]:
    planned: list[PlannedExperiment] = []
    counter = 1

    theorem_entries = [entry for entry in entries if entry.kind == "theorem"]
    empirical_entries = [entry for entry in entries if entry.kind == "empirical"]

    for entry in theorem_entries:
        experiment_id = f"EXP{counter:03d}"
        planned.append(
            PlannedExperiment(
                experiment_id=experiment_id,
                title=f"Synthetic validation for {entry.label}",
                category="synthetic",
                claim_id=entry.claim_id,
                target_label=entry.label,
                objective="Test whether the theorem's qualitative prediction appears under a controlled synthetic regime.",
                design="Construct a parameterized synthetic setting aligned with the stated assumptions and vary the regime where the theorem should hold or fail sharply.",
                failure_meaning="If the predicted qualitative behavior does not appear in the theorem regime, revisit the assumptions, statement scope, or proof outline.",
                data_need="synthetic",
                priority="high",
            )
        )
        counter += 1

    if "public_real_data" in spec.dataset_needs or "real_data" in spec.dataset_needs:
        anchor = theorem_entries[0] if theorem_entries else (empirical_entries[0] if empirical_entries else None)
        if anchor is not None:
            category = "public_real_data" if "public_real_data" in spec.dataset_needs else "real_data"
            experiment_id = f"EXP{counter:03d}"
            planned.append(
                PlannedExperiment(
                    experiment_id=experiment_id,
                    title=f"Real-data demonstration for {anchor.label}",
                    category=category,
                    claim_id=anchor.claim_id,
                    target_label=anchor.label,
                    objective="Check whether the proposed method or theorem-guided prediction remains informative on a realistic public or user-supplied dataset.",
                    design="Identify one benchmark dataset whose measurement regime roughly matches the theoretical setting, then compare the intended qualitative behavior against a baseline analysis.",
                    failure_meaning="If the real-data behavior conflicts with the theorem regime, clarify whether the issue is model misspecification, assumption mismatch, or a genuine limitation.",
                    data_need=category,
                    priority="medium",
                )
            )
            counter += 1

    for entry in empirical_entries:
        experiment_id = f"EXP{counter:03d}"
        planned.append(
            PlannedExperiment(
                experiment_id=experiment_id,
                title=f"Ablation for {entry.label}",
                category="synthetic" if "synthetic" in spec.dataset_needs else "analysis",
                claim_id=entry.claim_id,
                target_label=entry.label,
                objective="Stress-test the empirical claim against the theorem-led explanation.",
                design="Remove or weaken the key mechanism identified in the theory section and compare the qualitative degradation against the stated validation claim.",
                failure_meaning="If the ablation does not degrade behavior as expected, tighten the interpretive claim or revise the experiment design.",
                data_need="synthetic" if "synthetic" in spec.dataset_needs else "not_specified",
                priority="medium",
            )
        )
        counter += 1

    if not planned:
        planned.append(
            PlannedExperiment(
                experiment_id="EXP001",
                title="Foundational synthetic study",
                category="synthetic",
                claim_id=spec.core_claims[0].id if spec.core_claims else "C1",
                target_label="Main Claim",
                objective="Establish a minimal experiment that can confirm or falsify the main technical narrative.",
                design="Build a toy regime consistent with the current notation and assumptions, then vary the key control parameter.",
                failure_meaning="If even the toy regime is unclear, the theory and experiment programs need to be reformulated together.",
                data_need="synthetic",
                priority="high",
            )
        )

    return planned


def render_experiment_plan(spec: PaperSpec, planned: list[PlannedExperiment]) -> str:
    lines = [
        "# Experiment Plan",
        "",
        f"- Working title: `{spec.title_working or 'Untitled'}`",
        f"- Contribution modes: `{', '.join(spec.contribution_type) or 'unspecified'}`",
        f"- Dataset needs: `{', '.join(spec.dataset_needs) or 'not specified'}`",
        f"- Planned studies: `{len(planned)}`",
        "",
        "## Claim Coverage",
    ]
    by_claim: dict[str, list[str]] = {}
    for item in planned:
        by_claim.setdefault(item.claim_id, []).append(item.experiment_id)
    if by_claim:
        for claim_id, experiment_ids in by_claim.items():
            lines.append(f"- `{claim_id}` -> {', '.join(experiment_ids)}")
    else:
        lines.append("- No claim coverage mapped yet.")

    lines.extend(["", "## Planned Studies"])
    for item in planned:
        lines.extend(
            [
                f"### {item.experiment_id}: {item.title}",
                f"- Claim ID: `{item.claim_id}`",
                f"- Target ledger item: `{item.target_label}`",
                f"- Category: `{item.category}`",
                f"- Priority: `{item.priority}`",
                f"- Objective: {item.objective}",
                f"- Design: {item.design}",
                f"- Failure meaning: {item.failure_meaning}",
                f"- Data need: `{item.data_need}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_results_registry(project_root: Path, planned: list[PlannedExperiment]) -> dict[str, list[dict]]:
    runs = [
        ExperimentRunRecord(
            run_id=item.experiment_id.lower(),
            claim_ids=[item.claim_id],
            session_name=f"gwmos-{item.experiment_id.lower()}",
            script="",
            instruction_file=str((project_root / f"04_experiments/jobs/{item.experiment_id.lower()}.md").relative_to(project_root)),
            inputs=[],
            outputs=[],
            seed=42 if item.category == "synthetic" else None,
            status="planned",
        ).model_dump(mode="json")
        for item in planned
    ]
    return {"runs": runs}


def _load_spec(project_root: Path) -> PaperSpec:
    spec_path = project_root / "01_spec/paper_spec.yaml"
    return PaperSpec.model_validate(yaml.safe_load(spec_path.read_text(encoding="utf-8")))


def _write_instruction_files(project_root: Path, planned: list[PlannedExperiment]) -> None:
    job_root = project_root / "04_experiments/jobs"
    job_root.mkdir(parents=True, exist_ok=True)
    for item in planned:
        instruction_path = job_root / f"{item.experiment_id.lower()}.md"
        if instruction_path.exists():
            continue
        fallback = "\n".join(
            [
                f"# {item.experiment_id}: {item.title}",
                "",
                "## Experiment Goal",
                item.objective,
                "",
                "## Claim Mapping",
                f"- Claim ID: `{item.claim_id}`",
                f"- Target ledger item: `{item.target_label}`",
                "",
                "## Design",
                item.design,
                "",
                "## Failure Meaning",
                item.failure_meaning,
                "",
                "## Execution Expectations",
                f"- Category: `{item.category}`",
                f"- Data need: `{item.data_need}`",
                "- Use the local environment only.",
                "- Write concrete outputs under `04_experiments/outputs/<run_id>/`.",
                "- If dataset files are missing, stop and report the missing requirement clearly.",
                "- Do not invent successful numbers or figures.",
                "",
            ]
        )
        generated = complete_with_openai(
            project_root=project_root,
            prompt_path="agents/experiment.md",
            prompt=(
                "Write an experiment instruction markdown file for this planned validation task.\n\n"
                f"Experiment ID: {item.experiment_id}\n"
                f"Title: {item.title}\n"
                f"Claim ID: {item.claim_id}\n"
                f"Target: {item.target_label}\n"
                f"Category: {item.category}\n"
                f"Objective: {item.objective}\n"
                f"Design: {item.design}\n"
                f"Failure meaning: {item.failure_meaning}\n"
                f"Data need: {item.data_need}\n"
            ),
            fallback=fallback,
            max_output_tokens=1000,
        )
        write_text(instruction_path, generated if generated.startswith("#") else fallback)
