from __future__ import annotations

from enum import Enum


class Stage(str, Enum):
    intake = "intake"
    spec = "spec"
    novelty = "novelty"
    journal_fit = "journal_fit"
    theory_program = "theory_program"
    proof_audit = "proof_audit"
    experiment_design = "experiment_design"
    scaffold_draft = "scaffold_draft"
    experiment_run = "experiment_run"
    alignment_review = "alignment_review"
    final_write = "final_write"
    build_qa = "build_qa"

    @classmethod
    def ordered(cls) -> list["Stage"]:
        return [
            cls.intake,
            cls.spec,
            cls.novelty,
            cls.journal_fit,
            cls.theory_program,
            cls.proof_audit,
            cls.experiment_design,
            cls.scaffold_draft,
            cls.experiment_run,
            cls.alignment_review,
            cls.final_write,
            cls.build_qa,
        ]
