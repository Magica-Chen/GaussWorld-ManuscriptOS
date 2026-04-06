from __future__ import annotations

import time
from pathlib import Path
import shlex
from subprocess import CalledProcessError, run

from gw_mos.experiments.materialize import materialize_experiment_script
from gw_mos.utils.json_io import load_json, save_json


class TmuxRunner:
    def register_job(self, jobs_path: Path, job_id: str, session_name: str, log_path: str = "", status: str = "registered") -> None:
        payload = load_json(jobs_path) if jobs_path.exists() else {"jobs": []}
        jobs = payload.setdefault("jobs", [])
        for job in jobs:
            if job["job_id"] == job_id:
                job.update({"tmux_session": session_name, "status": status, "log_path": log_path})
                save_json(jobs_path, payload)
                return
        jobs.append({"job_id": job_id, "tmux_session": session_name, "status": status, "log_path": log_path})
        save_json(jobs_path, payload)

    def start_jobs(self, project_root: Path, job_ids: list[str] | None = None) -> list[str]:
        registry_path = project_root / "04_experiments/results_registry.json"
        jobs_path = project_root / "runtime/tmux_jobs.json"
        payload = load_json(registry_path)
        started: list[str] = []
        for run_record in payload.get("runs", []):
            run_id = run_record.get("run_id", "")
            if job_ids and run_id not in job_ids:
                continue
            if run_record.get("status") not in {"planned", "failed", "stopped"}:
                continue
            script_rel = run_record.get("script", "")
            if not script_rel:
                generated = materialize_experiment_script(project_root=project_root, run_record=run_record)
                if generated:
                    run_record["script"] = generated
                    script_rel = generated
            script_path = project_root / script_rel if script_rel else None
            if script_path is None or not script_path.exists():
                run_record["status"] = "awaiting_generation"
                continue
            session_name = run_record.get("session_name") or f"gwmos-{run_id}"
            log_path = project_root / f"04_experiments/outputs/{run_id}.log"
            exit_path = project_root / f"04_experiments/outputs/{run_id}.exitcode"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if self._session_exists(session_name):
                self.register_job(jobs_path=jobs_path, job_id=run_id, session_name=session_name, log_path=str(log_path), status="running")
                run_record["status"] = "running"
                started.append(run_id)
                continue
            command = (
                f"cd {shlex.quote(str(project_root))} && "
                f"bash {shlex.quote(str(script_path))} > {shlex.quote(str(log_path))} 2>&1; "
                f"printf '%s' $? > {shlex.quote(str(exit_path))}"
            )
            run(["tmux", "new-session", "-d", "-s", session_name, command], check=True, text=True)
            run_record["status"] = "running"
            self.register_job(jobs_path=jobs_path, job_id=run_id, session_name=session_name, log_path=str(log_path), status="running")
            started.append(run_id)
        save_json(registry_path, payload)
        self.sync_status(project_root)
        return started

    def sync_status(self, project_root: Path) -> dict[str, str]:
        registry_path = project_root / "04_experiments/results_registry.json"
        jobs_path = project_root / "runtime/tmux_jobs.json"
        payload = load_json(registry_path)
        jobs_payload = load_json(jobs_path) if jobs_path.exists() else {"jobs": []}
        jobs_index = {job["job_id"]: job for job in jobs_payload.get("jobs", [])}
        summary: dict[str, str] = {}
        for run_record in payload.get("runs", []):
            run_id = run_record.get("run_id", "")
            session_name = run_record.get("session_name") or f"gwmos-{run_id}"
            exit_path = project_root / f"04_experiments/outputs/{run_id}.exitcode"
            if self._session_exists(session_name):
                run_record["status"] = "running"
                job = jobs_index.setdefault(run_id, {"job_id": run_id, "tmux_session": session_name})
                job["status"] = "running"
            elif exit_path.exists():
                code = exit_path.read_text(encoding="utf-8").strip() or "1"
                status = "completed" if code == "0" else "failed"
                run_record["status"] = status
                job = jobs_index.setdefault(run_id, {"job_id": run_id, "tmux_session": session_name})
                job["status"] = status
            summary[run_id] = run_record.get("status", "unknown")
        jobs_payload["jobs"] = list(jobs_index.values())
        save_json(registry_path, payload)
        save_json(jobs_path, jobs_payload)
        return summary

    def wait_for_quiescence(self, project_root: Path, timeout_seconds: float = 2.0, poll_interval: float = 0.2) -> dict[str, str]:
        deadline = time.monotonic() + timeout_seconds
        summary = self.sync_status(project_root)
        while time.monotonic() < deadline and any(status == "running" for status in summary.values()):
            time.sleep(poll_interval)
            summary = self.sync_status(project_root)
        return summary

    def get_logs(self, project_root: Path, job_id: str, lines: int = 80) -> str:
        log_path = project_root / f"04_experiments/outputs/{job_id}.log"
        if not log_path.exists():
            return f"No log file found for {job_id}."
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = content[-lines:]
        return "\n".join(tail) + ("\n" if tail else "")

    def stop_job(self, project_root: Path, job_id: str) -> str:
        registry_path = project_root / "04_experiments/results_registry.json"
        jobs_path = project_root / "runtime/tmux_jobs.json"
        payload = load_json(registry_path)
        session_name = None
        for run_record in payload.get("runs", []):
            if run_record.get("run_id") == job_id:
                session_name = run_record.get("session_name") or f"gwmos-{job_id}"
                break
        if not session_name:
            raise ValueError(f"Unknown experiment job: {job_id}")
        if self._session_exists(session_name):
            run(["tmux", "kill-session", "-t", session_name], check=True, text=True)
        for run_record in payload.get("runs", []):
            if run_record.get("run_id") == job_id:
                run_record["status"] = "stopped"
        save_json(registry_path, payload)
        self.register_job(jobs_path=jobs_path, job_id=job_id, session_name=session_name, status="stopped")
        return session_name

    def status_summary(self, project_root: Path) -> str:
        summary = self.sync_status(project_root)
        if not summary:
            return "No experiment jobs registered."
        return "\n".join(f"{job_id}: {status}" for job_id, status in sorted(summary.items())) + "\n"

    def _session_exists(self, session_name: str) -> bool:
        try:
            run(["tmux", "has-session", "-t", session_name], check=True, text=True, capture_output=True)
            return True
        except CalledProcessError:
            return False
