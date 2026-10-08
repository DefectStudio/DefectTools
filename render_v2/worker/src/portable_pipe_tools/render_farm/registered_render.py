"""Render a job using only an explicitly registered local project.

Updates the registered Git checkout and assets before rendering; no project discovery or clone.
Input jobs and live queues remain unchanged; each run gets isolated outputs.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4

from portable_pipe_tools.app_runtime import default_settings_path
from portable_pipe_tools.render_farm.project_render import install_runtime
from portable_pipe_tools.render_farm.project_workspace import project_lock, PreparationCancelled
from portable_pipe_tools.render_farm.registered_sync import sync_registered_project, SYNC_POLICY
from portable_pipe_tools.render_farm.queue import read_json_object, write_json_atomic
from portable_pipe_tools.render_farm.unreal_runner import execute_unreal_job, validate_real_render_job
from portable_pipe_tools.render_farm.v2_gui_settings import load_registered_projects


def local_project_lock(uproject: Path) -> Path:
    """Share the legacy checkout lock, or use Saved for a non-Git project."""
    if shutil.which("git"):
        result = subprocess.run(["git", "rev-parse", "--git-path", "render-worker.lock"],
                                cwd=uproject.parent, capture_output=True, text=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode == 0:
            path = Path(result.stdout.strip())
            return path if path.is_absolute() else uproject.parent / path
    return uproject.parent / "Saved/RenderWorkerV2/render-worker.lock"


def prepare_registered_job(settings_path: Path, project_id: str, job_path: Path):
    projects = load_registered_projects(settings_path)
    project = next((item for item in projects if item.project_id.casefold() == project_id.casefold()), None)
    if project is None:
        raise ValueError(f"Project is not registered on this worker: {project_id}")
    uproject = Path(project.local_uproject).resolve()
    farm = Path(project.render_farm_root).resolve()
    if not uproject.is_file():
        raise ValueError(f"Registered Unreal project is unavailable: {uproject}")
    read_json_object(uproject)
    if not farm.is_dir():
        raise ValueError(f"Registered renderFarm folder is unavailable: {farm}")
    if farm.parent.name.casefold() != project.project_id.casefold():
        raise ValueError("Re-select this registration's Dropbox show: its ID must match the show folder.")
    engine_value = read_json_object(settings_path).get("unreal_editor_cmd", "")
    if not isinstance(engine_value, str):
        raise ValueError("Choose an existing UnrealEditor-Cmd.exe in the worker settings.")
    engine = Path(engine_value).expanduser()
    if not engine.is_absolute() or not engine.is_file() or engine.name.casefold() != "unrealeditor-cmd.exe":
        raise ValueError("Choose an existing UnrealEditor-Cmd.exe in the worker settings.")
    job = deepcopy(read_json_object(job_path))
    identity = job.get("project_id") or job.get("project")
    if not isinstance(identity, str) or identity.casefold() != project.project_id.casefold():
        raise ValueError(f"Job project {identity!r} does not match registered show {project.project_id!r}.")
    shot = job.get("shot_name", "")
    if not isinstance(shot, str) or not re.fullmatch(r"[A-Za-z0-9_]+", shot):
        raise ValueError("Job must contain a shot_name using letters, numbers and underscores.")
    job.update(status="rendering", uproject=str(uproject))
    validate_real_render_job(job, uproject)
    overrides = job["graph_variable_overrides"]
    if not all(isinstance(key, str) and isinstance(payload, dict) for key, payload in overrides.items()):
        raise ValueError("Graph overrides must contain named override objects.")
    names = {key.casefold() for key in overrides}
    if not {"outputdirectory", "filenameformat"}.issubset(names):
        raise ValueError("The job must expose OutputDirectory and FileNameFormat graph overrides.")
    return project, uproject, engine, job


def render_registered_job(settings_path: Path, project_id: str, job_path: Path, *,
                          output_root: Path | None = None, timeout_seconds=7200,
                          progress=print, cancelled=lambda: False) -> dict:
    if not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Render timeout must be positive and finite.")
    project, uproject, engine, job = prepare_registered_job(settings_path, project_id, job_path)
    if cancelled():
        raise PreparationCancelled("Render cancelled before preparation")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    base = output_root or Path(project.render_farm_root).parent / "WorkerV2Renders"
    run_root = Path(base).resolve() / project.project_id / job["shot_name"] / run_id
    with project_lock(local_project_lock(uproject)):
        job_folder = run_root / "job"
        job_folder.mkdir(parents=True, exist_ok=False)
        (run_root / "renderFarm").mkdir()
        progress(f"Registered project: {uproject}; updating before rendering.")
        progress(f"Run folder: {run_root}")
        summary = {"success": False, "project_id": project.project_id,
                   "shot": job["shot_name"], "run_root": str(run_root),
                   "source_job": str(Path(job_path).resolve()), "sync_policy": SYNC_POLICY}
        try:
            original_id = job["job_id"]
            job.update(job_id=f"{project.project_id}_{job['shot_name']}_{run_id}", source_job_id=original_id,
                       project=project.project_id, project_id=project.project_id,
                       worker_runtime_version=2, disable_project_scripts=False,
                       worker_sync_policy=SYNC_POLICY,
                       output_directory=str(run_root / "output"), output_relative_directory="output",
                       submitted_show_file_server_path=str(run_root),
                       submitted_output_directory=str(run_root / "output"))
            # Replays cannot retain machine paths, commit requirements or output filenames from earlier attempts.
            for key in ("prepared_git_commit", "git_commit_after_pull", "worker_output_directory",
                        "worker_show_file_server_path", "rendered_git_commit"):
                job.pop(key, None)
            job["output_file_name_format"] = "EXR/" + job["shot_name"] + ".{frame_number}"
            job["mp4_file_name_format"] = job["shot_name"]
            for key, payload in job["graph_variable_overrides"].items():
                if key.casefold() == "outputdirectory":
                    payload.update(enabled=True)
                elif key.casefold() in ("filenameformat", "mp4filenameformat"):
                    value = job["output_file_name_format"] if key.casefold() == "filenameformat" else job["shot_name"]
                    payload.update(enabled=True, serialized_value=value)
            commit = sync_registered_project(uproject, run_root / "project-sync", progress=progress, cancelled=cancelled)
            job.update(prepared_git_commit=commit, git_commit_after_pull=commit)
            summary["git_commit_after_pull"] = commit
            write_json_atomic(job_folder / "job.json", job)
            if cancelled():
                raise PreparationCancelled("Render cancelled before runtime installation")
            install_runtime(uproject.parent, project_directory=uproject.parent)
            if cancelled():
                raise PreparationCancelled("Render cancelled before Unreal launch")
            progress(f"Rendering {job['shot_name']} with {engine}")
            result = execute_unreal_job(job_folder, job, unreal_editor_cmd=engine, local_uproject=uproject,
                                        render_farm_root=run_root / "renderFarm", timeout_seconds=timeout_seconds,
                                        should_cancel=cancelled)
            summary.update(success=result.success, reason=result.reason, cancelled=result.cancelled,
                           render=result.terminal_result_details())
            summary["render"].pop("git_pull_log_file", None)
        except Exception as error:
            summary.update(reason=str(error), cancelled=isinstance(error, PreparationCancelled))
            raise
        finally:
            write_json_atomic(run_root / "result.json", summary)
            progress(f"Result receipt: {run_root / 'result.json'}")
        return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=default_settings_path())
    parser.add_argument("--project", required=True)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--timeout", type=float, default=7200)
    args = parser.parse_args(argv)
    try:
        result = render_registered_job(args.settings, args.project, args.job, output_root=args.output_root,
                                       timeout_seconds=args.timeout, progress=lambda text: print(text, flush=True))
        print(json.dumps(result, indent=2))
        return 0 if result["success"] else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Render Worker: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
