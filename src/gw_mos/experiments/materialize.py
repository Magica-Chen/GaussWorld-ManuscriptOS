from __future__ import annotations

import re
from pathlib import Path

from gw_mos.artifacts.writers import write_text
from gw_mos.prompt_loader import load_prompt
from gw_mos.providers.base import ProviderError, ProviderRequest
from gw_mos.providers.registry import build_provider, provider_available


def materialize_experiment_script(project_root: Path, run_record: dict) -> str | None:
    instruction_rel = run_record.get("instruction_file", "")
    if not instruction_rel:
        return None
    instruction_path = project_root / instruction_rel
    if not instruction_path.exists():
        return None
    run_id = run_record.get("run_id", "run")
    generated_root = project_root / "04_experiments/generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    script_path = generated_root / f"{run_id}.sh"

    if provider_available("openai", start=project_root):
        script_text = _generate_script_with_provider(project_root=project_root, run_id=run_id, instruction_path=instruction_path)
    else:
        script_text = _fallback_script(run_id=run_id, instruction_path=instruction_path)

    write_text(script_path, script_text)
    script_path.chmod(0o755)
    return str(script_path.relative_to(project_root))


def _generate_script_with_provider(project_root: Path, run_id: str, instruction_path: Path) -> str:
    provider = build_provider("openai", start=project_root)
    instruction_text = instruction_path.read_text(encoding="utf-8")
    prompt = (
        f"project_root={project_root}\n"
        f"run_id={run_id}\n"
        "Instruction file contents:\n"
        f"{instruction_text}"
    )
    try:
        response = provider.generate(
            ProviderRequest(
                prompt=prompt,
                system_prompt=load_prompt(
                    "agents/experiment_runner.md",
                    fallback="Return only a runnable bash script for the experiment.",
                ),
                max_output_tokens=1400,
            )
        )
    except ProviderError:
        return _fallback_script(run_id=run_id, instruction_path=instruction_path)
    return _strip_fences(response.content) or _fallback_script(run_id=run_id, instruction_path=instruction_path)


def _fallback_script(run_id: str, instruction_path: Path) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"echo \"gw-mos could not materialize a real script for {run_id}.\"",
            f"echo \"Read the instruction file: {instruction_path}\"",
            "echo \"Configure OpenAI credentials to allow on-demand experiment script generation.\"",
            "exit 2",
            "",
        ]
    )


def _strip_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped)
    return stripped.strip()
