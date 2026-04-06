from __future__ import annotations

from dataclasses import asdict, dataclass, field

from gw_mos.controller.stages import Stage


@dataclass
class RoutedPlan:
    init_project: bool = False
    project_name: str | None = None
    journal: str = "custom"
    stages: list[Stage] = field(default_factory=list)
    ingest_literature: bool = False
    search_public_literature: bool = False
    literature_query: str | None = None
    show_status: bool = False
    show_journal: bool = False
    show_qa: bool = False
    show_readiness: bool = False
    show_bundle: bool = False
    explanation: str = ""
    source: str = "deterministic"
    assistant_reply: str = ""
    review_note: str = ""

    def copy(self) -> "RoutedPlan":
        return RoutedPlan(
            init_project=self.init_project,
            project_name=self.project_name,
            journal=self.journal,
            stages=list(self.stages),
            ingest_literature=self.ingest_literature,
            search_public_literature=self.search_public_literature,
            literature_query=self.literature_query,
            show_status=self.show_status,
            show_journal=self.show_journal,
            show_qa=self.show_qa,
            show_readiness=self.show_readiness,
            show_bundle=self.show_bundle,
            explanation=self.explanation,
            source=self.source,
            assistant_reply=self.assistant_reply,
            review_note=self.review_note,
        )

    def to_payload(self) -> dict:
        payload = asdict(self)
        payload["stages"] = [stage.value for stage in self.stages]
        return payload

    @classmethod
    def from_payload(cls, payload: dict) -> "RoutedPlan":
        stages: list[Stage] = []
        for stage_value in payload.get("stages", []):
            try:
                stages.append(Stage(stage_value))
            except ValueError:
                continue
        return cls(
            init_project=bool(payload.get("init_project", False)),
            project_name=payload.get("project_name"),
            journal=payload.get("journal", "custom"),
            stages=stages,
            ingest_literature=bool(payload.get("ingest_literature", False)),
            search_public_literature=bool(payload.get("search_public_literature", False)),
            literature_query=payload.get("literature_query"),
            show_status=bool(payload.get("show_status", False)),
            show_journal=bool(payload.get("show_journal", False)),
            show_qa=bool(payload.get("show_qa", False)),
            show_readiness=bool(payload.get("show_readiness", False)),
            show_bundle=bool(payload.get("show_bundle", False)),
            explanation=str(payload.get("explanation", "")),
            source=str(payload.get("source", "openai")),
            assistant_reply=str(payload.get("assistant_reply", "")),
            review_note=str(payload.get("review_note", "")),
        )

    def is_low_confidence(self) -> bool:
        return (
            not self.init_project
            and not self.stages
            and not self.ingest_literature
            and not self.search_public_literature
            and self.show_status
            and self.explanation.startswith("No strong intent match")
        )
