from __future__ import annotations

import webbrowser
from pathlib import Path

import typer
import yaml

from gw_mos.auth.oauth_openai import OpenAIOAuthConfig, build_login_session, capture_callback_code, create_profile_from_token_payload
from gw_mos.auth.profile_store import AuthProfile
from gw_mos.auth.service import list_profiles, upsert_profile
from gw_mos.controller.engine import ControllerEngine
from gw_mos.controller.stages import Stage
from gw_mos.experiments.runner_tmux import TmuxRunner
from gw_mos.journals.discovery import resolve_template
from gw_mos.literature.pipeline import ingest_literature, search_and_ingest_public_metadata
from gw_mos.nl import execute_request, help_text
from gw_mos.session import start_interactive_session

app = typer.Typer(help="Artefact-driven research paper workflow CLI.", no_args_is_help=False, invoke_without_command=True)
auth_app = typer.Typer(help="Authentication commands.")
journal_app = typer.Typer(help="Journal pack commands.")
literature_app = typer.Typer(help="Literature ingestion commands.")
stage_app = typer.Typer(help="Workflow stage commands.")
exp_app = typer.Typer(help="Experiment runner commands.")
qa_app = typer.Typer(help="QA commands.")

app.add_typer(auth_app, name="auth")
app.add_typer(journal_app, name="journal")
app.add_typer(literature_app, name="literature")
app.add_typer(stage_app, name="stage")
app.add_typer(exp_app, name="exp")
app.add_typer(qa_app, name="qa")


@app.callback(invoke_without_command=True)
def app_callback(
    ctx: typer.Context,
    project: Path | None = typer.Option(None, "--project", help="Project to attach when opening the interactive shell."),
    root: Path = typer.Option(Path("."), "--root", help="Root directory for new projects in interactive mode."),
    journal: str = typer.Option("custom", "--journal", help="Default journal family for interactive mode."),
    template: Path | None = typer.Option(None, "--template", help="Default template path for interactive mode."),
) -> None:
    if ctx.invoked_subcommand is None:
        start_interactive_session(project=project, root=root, journal=journal, template=template)
        raise typer.Exit()


@app.command()
def init(
    project_name: str,
    journal: str = typer.Option("custom", help="Journal family or adapter name."),
    template: Path | None = typer.Option(None, help="Optional journal template directory."),
    root: Path = typer.Option(Path("."), help="Root directory where the project will be created."),
) -> None:
    engine = ControllerEngine()
    project_root = engine.initialise_project(root=root, project_name=project_name, journal=journal, template=template)
    typer.echo(f"Initialized project at {project_root}")


@app.command()
def status(project_path: Path) -> None:
    engine = ControllerEngine()
    typer.echo(engine.render_status(project_path))


@app.command()
def resume(project_path: Path) -> None:
    engine = ControllerEngine()
    state = engine.get_state(project_path)
    typer.echo(f"Current stage: {state.current_stage}. Status: {state.stage_status}.")


@app.command()
def run(
    request: str,
    project: Path | None = typer.Option(None, "--project", help="Existing project path."),
    root: Path = typer.Option(Path("."), help="Root directory for new projects."),
    name: str | None = typer.Option(None, "--name", help="Project name override for init-like requests."),
    journal: str = typer.Option("custom", help="Journal family override for init-like requests."),
    template: Path | None = typer.Option(None, "--template", help="Template path for init-like requests."),
    pdf: list[Path] = typer.Option(None, "--pdf", help="PDF files for literature-ingest requests."),
    bib: list[Path] = typer.Option(None, "--bib", help="BibTeX files for literature-ingest requests."),
) -> None:
    if request.strip().lower() in {"help", "?", "examples"}:
        typer.echo(help_text())
        return
    result = execute_request(
        request=request,
        project_path=project,
        root=root,
        project_name=name,
        journal=journal,
        template=template,
        bib_paths=bib or [],
        pdf_paths=pdf or [],
    )
    typer.echo(result.output, nl=False)


@app.command()
def chat(
    project: Path | None = typer.Option(None, "--project", help="Existing project path."),
    root: Path = typer.Option(Path("."), help="Root directory for newly initialized projects."),
    journal: str = typer.Option("custom", help="Default journal family for init-like requests."),
    template: Path | None = typer.Option(None, "--template", help="Template path for init-like requests."),
) -> None:
    start_interactive_session(project=project, root=root, journal=journal, template=template)


@auth_app.command("login")
def auth_login(
    provider: str,
    client_id: str | None = typer.Option(None, "--client-id", help="OpenAI OAuth client ID."),
    profile_id: str = typer.Option("default", "--profile", help="Profile identifier."),
    account_label: str = typer.Option("openai-oauth", "--label", help="Human-readable account label."),
    open_browser: bool = typer.Option(True, "--open-browser/--no-browser", help="Attempt to open the browser automatically."),
) -> None:
    if provider != "openai":
        raise typer.BadParameter("Only `openai` supports the login flow in v1. Use `gw-mos auth add` for API-key profiles.")
    resolved_client_id = client_id or typer.prompt("OpenAI OAuth client ID", default="", show_default=False).strip()
    if not resolved_client_id:
        raise typer.BadParameter("An OpenAI OAuth client ID is required.")

    config = OpenAIOAuthConfig(client_id=resolved_client_id)
    authorize_url, state, verifier = build_login_session(config)
    typer.echo(f"Authorization URL:\n{authorize_url}\n")
    if open_browser:
        webbrowser.open(authorize_url, new=2)
    code = capture_callback_code(config=config, expected_state=state, timeout_seconds=180)
    if not code:
        pasted = typer.prompt("Paste the full callback URL or the authorization code", default="", show_default=False).strip()
        code = _extract_code(pasted)
    if not code:
        raise typer.BadParameter("Could not obtain an authorization code from the callback or manual input.")
    payload = _exchange_openai_code(config=config, code=code, verifier=verifier)
    profile = create_profile_from_token_payload(
        payload,
        profile_id=profile_id,
        account_label=account_label,
        client_id=resolved_client_id,
        provenance="oauth:interactive-login",
    )
    path = upsert_profile(profile)
    typer.echo(f"Stored OpenAI profile `{profile.profile_id}` at {path}")


@auth_app.command("add")
def auth_add(
    provider: str,
    profile_id: str = typer.Option("default", "--profile", help="Profile identifier."),
    account_label: str = typer.Option("", "--label", help="Human-readable account label."),
    api_key: str | None = typer.Option(None, "--api-key", help="API key to store locally."),
    model: str | None = typer.Option(None, "--model", help="Default model override."),
) -> None:
    if provider not in {"openai", "anthropic"}:
        raise typer.BadParameter("Supported providers are `openai` and `anthropic`.")
    secret = api_key or typer.prompt(f"{provider} API key", hide_input=True)
    if not secret:
        raise typer.BadParameter("An API key is required.")
    profile = AuthProfile(
        provider=provider,
        profile_id=profile_id,
        account_label=account_label or f"{provider}-api-key",
        auth_type="api_key",
        api_key=secret,
        provenance="api_key:manual",
        model=model,
    )
    path = upsert_profile(profile)
    typer.echo(f"Stored {provider} profile `{profile.profile_id}` at {path}")


@auth_app.command("list")
def auth_list() -> None:
    profiles = list_profiles()
    if not profiles:
        typer.echo("No local auth profiles configured.")
        return
    for profile in profiles:
        typer.echo(
            " | ".join(
                [
                    profile.provider,
                    profile.profile_id,
                    profile.auth_type,
                    profile.account_label or "n/a",
                    profile.masked_secret() or "no-secret",
                    profile.expires_at or "no-expiry",
                    profile.provenance or "local",
                ]
            )
        )


@journal_app.command("inspect")
def journal_inspect(project_path: Path) -> None:
    engine = ControllerEngine()
    state = engine.get_state(project_path)
    inspection = resolve_template(
        journal_family=state.journal_family,
        project_root=project_path,
        explicit_template=state.template_path,
    )
    typer.echo(yaml.safe_dump(inspection.model_dump(mode="json"), sort_keys=False))


@literature_app.command("ingest")
def literature_ingest(
    project_path: Path,
    pdf: list[Path] = typer.Option(None, "--pdf", help="Local PDFs to ingest."),
    bib: list[Path] = typer.Option(None, "--bib", help="BibTeX files to ingest."),
) -> None:
    summary = ingest_literature(project_root=project_path, pdf_paths=pdf or [], bib_paths=bib or [])
    typer.echo(
        "\n".join(
            [
                f"project={project_path}",
                f"bib_files={summary.bib_files}",
                f"pdf_files={summary.pdf_files}",
                f"grounded_entries={summary.grounded_entries}",
                f"provisional_entries={summary.provisional_entries}",
                f"notes_written={summary.notes_written}",
            ]
        )
    )


@literature_app.command("search")
def literature_search(
    project_path: Path,
    query: str | None = typer.Option(None, "--query", help="Explicit metadata search query."),
    limit: int = typer.Option(6, "--limit", help="Maximum number of public metadata results to ingest."),
) -> None:
    summary = search_and_ingest_public_metadata(project_root=project_path, query=query, limit=limit)
    typer.echo(
        "\n".join(
            [
                f"project={project_path}",
                f"query={summary.query}",
                f"result_count={summary.result_count}",
                f"grounded_entries={summary.grounded_entries}",
                f"notes_written={summary.notes_written}",
            ]
        )
    )


@stage_app.command("run")
def stage_run(stage: Stage, project_path: Path) -> None:
    engine = ControllerEngine()
    state = engine.run_stage(project_path=project_path, stage=stage)
    typer.echo(f"Stage {state.current_stage} marked {state.stage_status}.")


@stage_app.command("run-all")
def stage_run_all(
    project_path: Path,
    until: Stage = typer.Option(Stage.build_qa, help="Run placeholder transitions through this stage."),
) -> None:
    engine = ControllerEngine()
    for stage in Stage.ordered():
        engine.run_stage(project_path=project_path, stage=stage)
        if stage == until:
            break
    typer.echo(f"Completed placeholder transitions through {until.value}.")


@exp_app.command("start")
def exp_start(
    project_path: Path,
    job: list[str] = typer.Option(None, "--job", help="Specific run_id entries to launch."),
) -> None:
    runner = TmuxRunner()
    started = runner.start_jobs(project_root=project_path, job_ids=job or None)
    if not started:
        typer.echo("No experiment jobs were started.")
        return
    typer.echo("Started experiment jobs:")
    for job_id in started:
        typer.echo(f"- {job_id}")


@exp_app.command("status")
def exp_status(project_path: Path) -> None:
    runner = TmuxRunner()
    typer.echo(runner.status_summary(project_root=project_path), nl=False)


@exp_app.command("logs")
def exp_logs(
    project_path: Path,
    job: str = typer.Option(..., "--job", help="Job ID to inspect."),
    follow: bool = typer.Option(False, "--follow"),
) -> None:
    if follow:
        raise typer.BadParameter("`--follow` is not implemented yet; use `gw-mos exp logs --job <id>` for a snapshot.")
    runner = TmuxRunner()
    typer.echo(runner.get_logs(project_root=project_path, job_id=job), nl=False)


@exp_app.command("stop")
def exp_stop(project_path: Path, job: str = typer.Option(..., help="Job ID to stop.")) -> None:
    runner = TmuxRunner()
    session_name = runner.stop_job(project_root=project_path, job_id=job)
    typer.echo(f"Stopped tmux session `{session_name}` for job `{job}`.")


@app.command()
def build(project_path: Path) -> None:
    engine = ControllerEngine()
    state = engine.run_stage(project_path=project_path, stage=Stage.build_qa)
    report_path = project_path / "06_qa/qa_report.md"
    typer.echo(f"Build stage marked {state.stage_status}. Report: {report_path}")
    if state.stage_status != "completed":
        raise typer.Exit(code=1)


@app.command()
def ready(project_path: Path) -> None:
    result = execute_request(
        request="prepare the paper to be submission ready",
        project_path=project_path,
        root=project_path.parent,
    )
    typer.echo(result.output, nl=False)


@qa_app.command("report")
def qa_report(project_path: Path) -> None:
    report_path = project_path / "06_qa/qa_report.md"
    if not report_path.exists():
        raise typer.BadParameter(f"QA report not found: {report_path}")
    typer.echo(report_path.read_text(encoding="utf-8"))


@qa_app.command("readiness")
def qa_readiness(project_path: Path) -> None:
    report_path = project_path / "06_qa/submission_readiness.md"
    if not report_path.exists():
        raise typer.BadParameter(f"Submission readiness report not found: {report_path}")
    typer.echo(report_path.read_text(encoding="utf-8"))


@qa_app.command("bundle")
def qa_bundle(project_path: Path) -> None:
    manifest_path = project_path / "07_submission/manifest.md"
    if not manifest_path.exists():
        raise typer.BadParameter(f"Submission bundle manifest not found: {manifest_path}")
    typer.echo(manifest_path.read_text(encoding="utf-8"))


def main() -> None:
    app()


def _exchange_openai_code(config: OpenAIOAuthConfig, code: str, verifier: str) -> dict:
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    import json
    from urllib.error import HTTPError, URLError

    request = Request(
        config.token_url,
        data=urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "code_verifier": verifier,
            }
        ).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise typer.BadParameter(f"OpenAI OAuth exchange failed: {exc.code} {detail}") from exc
    except URLError as exc:
        raise typer.BadParameter(f"OpenAI OAuth exchange failed: {exc.reason}") from exc


def _extract_code(value: str) -> str | None:
    if "code=" in value:
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(value)
        return (parse_qs(parsed.query).get("code") or [None])[0]
    return value or None
