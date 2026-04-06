from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from gw_mos.controller.stages import Stage


class ClaimClassification(str, Enum):
    proved = "proved"
    cited = "cited"
    experimentally_supported = "experimentally_supported"
    conjectural = "conjectural"
    editorial = "editorial"


class ClaimRecord(BaseModel):
    id: str
    text: str
    type: str = "claim"


class PaperSpec(BaseModel):
    title_working: str = ""
    problem_statement: str = ""
    contribution_type: list[str] = Field(default_factory=list)
    target_journal: str = ""
    journal_family: str = "custom"
    core_claims: list[ClaimRecord] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    dataset_needs: list[str] = Field(default_factory=list)


class CitationRecord(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    source_type: str = ""
    source_url: str = ""
    bibtex_key: str = ""
    verified: bool = False
    used_for_claims: list[str] = Field(default_factory=list)


class ExperimentRunRecord(BaseModel):
    run_id: str
    claim_ids: list[str] = Field(default_factory=list)
    session_name: str = ""
    script: str = ""
    instruction_file: str = ""
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    seed: int | None = None
    status: str = "pending"


class ProjectState(BaseModel):
    project_name: str
    journal_family: str = "custom"
    template_path: str | None = None
    current_stage: Stage = Stage.intake
    stage_status: str = "ready"
    completed_stages: list[Stage] = Field(default_factory=list)


class JobStatus(BaseModel):
    job_id: str
    tmux_session: str
    status: str = "pending"


class RuntimeStatus(BaseModel):
    project: str
    current_stage: Stage = Stage.intake
    stage_status: str = "ready"
    active_agent: str = "controller"
    active_jobs: list[JobStatus] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    last_build: dict[str, str] = Field(default_factory=dict)
    submission_ready: str = "unknown"
