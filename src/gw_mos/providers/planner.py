from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from gw_mos.controller.stages import Stage
from gw_mos.nl_types import RoutedPlan
from gw_mos.prompt_loader import load_prompt
from gw_mos.providers.base import ProviderError, ProviderRequest
from gw_mos.providers.registry import build_provider, provider_available


@dataclass
class ProviderPlanResult:
    plan: RoutedPlan
    planner_provider: str
    reviewer_provider: str | None = None
    review_note: str = ""


def maybe_plan_with_providers(
    *,
    request_text: str,
    deterministic_plan: RoutedPlan,
    current_stage: Stage | None,
    project_path: Path | None,
) -> ProviderPlanResult | None:
    if not provider_available("openai", start=project_path):
        return None

    provider = build_provider("openai", start=project_path)
    prompt = _planner_prompt(
        request_text=request_text,
        deterministic_plan=deterministic_plan,
        current_stage=current_stage,
        project_path=project_path,
    )
    try:
        response = provider.generate(
            ProviderRequest(
                prompt=prompt,
                system_prompt=_planner_system_prompt(),
                max_output_tokens=1200,
            )
        )
    except ProviderError:
        return None

    candidate = _parse_plan(response.content)
    if candidate is None:
        return None

    candidate.source = "openai"
    review_note = ""
    reviewer_provider: str | None = None

    if provider_available("anthropic", start=project_path):
        reviewer_provider = "anthropic"
        review_note = _review_plan(
            request_text=request_text,
            candidate=candidate,
            project_path=project_path,
        )
        if review_note.lower().startswith("reject:"):
            return None

    merged = _merge_plans(deterministic_plan=deterministic_plan, candidate=candidate)
    merged.review_note = review_note
    return ProviderPlanResult(
        plan=merged,
        planner_provider="openai",
        reviewer_provider=reviewer_provider,
        review_note=review_note,
    )


def _planner_system_prompt() -> str:
    fallback = (
        "You are the gw-mos planning model. "
        "Return a strict JSON object and nothing else. "
        "Plan only safe workflow actions for a research-paper project."
    )
    return load_prompt("agents/planner.md", fallback=fallback)


def _planner_prompt(
    *,
    request_text: str,
    deterministic_plan: RoutedPlan,
    current_stage: Stage | None,
    project_path: Path | None,
) -> str:
    context = {
        "request": request_text,
        "current_stage": current_stage.value if current_stage else None,
        "project_path": str(project_path) if project_path else None,
        "deterministic_plan": deterministic_plan.to_payload(),
    }
    return (
        "Produce a JSON object with these keys only: "
        "init_project, project_name, journal, stages, ingest_literature, search_public_literature, literature_query, "
        "show_status, show_journal, show_qa, explanation. "
        "The `stages` array must use only the allowed stage names. "
        f"Context:\n{json.dumps(context, indent=2)}"
    )


def _review_plan(request_text: str, candidate: RoutedPlan, project_path: Path | None) -> str:
    reviewer = build_provider("anthropic", start=project_path)
    prompt = (
        "Review the following gw-mos plan. "
        "Respond with a single line starting with either `approve:` or `reject:` followed by a brief reason.\n"
        f"Request: {request_text}\n"
        f"Plan: {json.dumps(candidate.to_payload(), indent=2)}"
    )
    try:
        response = reviewer.generate(
            ProviderRequest(
                prompt=prompt,
                system_prompt="You are a critical workflow reviewer. Be concise.",
                max_output_tokens=200,
            )
        )
    except ProviderError:
        return ""
    return response.content.strip()


def _parse_plan(text: str) -> RoutedPlan | None:
    payload = _extract_json_object(text)
    if payload is None:
        return None
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return RoutedPlan.from_payload(data)


def _extract_json_object(text: str) -> str | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    return match.group(0)


def _merge_plans(*, deterministic_plan: RoutedPlan, candidate: RoutedPlan) -> RoutedPlan:
    if deterministic_plan.is_low_confidence():
        return candidate
    merged = deterministic_plan.copy()
    if candidate.assistant_reply and not merged.assistant_reply:
        merged.assistant_reply = candidate.assistant_reply
    if candidate.explanation:
        merged.explanation = candidate.explanation
    return merged
