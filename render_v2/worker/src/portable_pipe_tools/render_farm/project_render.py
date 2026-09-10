"""Turn a prepared project and shot name into an isolated real render."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from uuid import uuid4

from portable_pipe_tools.app_runtime import resource_root

from portable_pipe_tools.render_farm.project_workspace import PreparedProject, PreparationCancelled
from portable_pipe_tools.render_farm.unreal_runner import execute_unreal_job


def install_runtime(checkout: Path, *, project_directory: Path | None = None) -> None:
    source = resource_root() / "unreal/RenderWorkerRuntime"
    target = (project_directory or checkout) / "Plugins/RenderWorkerRuntime"
    if not target.resolve().is_relative_to(checkout.resolve()):
        raise RuntimeError("Runtime plugin must stay inside the managed checkout")
    marker = target / ".render-worker-runtime"
    if target.exists() and not marker.is_file():
        raise RuntimeError("Refusing to overwrite an unmanaged RenderWorkerRuntime plugin")
    target.mkdir(parents=True, exist_ok=True)
    marker.write_text("Managed by Render Worker V2\n", encoding="utf-8")
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # Copied projects are supported too; Git is optional and never fetches here.
    if shutil.which("git") is None:
        return
    git_result = subprocess.run(["git", "rev-parse", "--git-path", "info/exclude"], cwd=checkout,
                               capture_output=True, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if git_result.returncode != 0:
        return
    exclude_path = git_result.stdout.strip()
    exclude = Path(exclude_path)
    if not exclude.is_absolute():
        exclude = checkout / exclude
    contents = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    git_root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=checkout,
                              capture_output=True, text=True, check=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    pattern = "/" + target.resolve().relative_to(Path(git_root).resolve()).as_posix() + "/"
    if pattern not in contents.splitlines():
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as stream:
            stream.write("\n" + pattern + "\n")


def render_project_shot(prepared: PreparedProject, shot: str, output_root: Path, *, progress=print,
                        cancelled=lambda: False, timeout_seconds=7200) -> dict:
    shot = prepared.project.canonical_shot(shot)
    repository = resource_root()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    run_root = output_root.resolve() / prepared.project.project_id / shot / run_id
    job_folder = run_root / "job"
    job_folder.mkdir(parents=True)
    (run_root / "renderFarm").mkdir()
    progress("Installing the worker's minimal Unreal runtime")
    install_runtime(prepared.checkout, project_directory=prepared.uproject.parent)
    request = {
        "job_id": f"{prepared.project.project_id}_{shot}_{run_id}", "shot": shot,
        "project_id": prepared.project.project_id, "project_name": prepared.uproject.stem,
        "checkout": str(prepared.checkout), "uproject": str(prepared.uproject),
        "project_directory": str(prepared.uproject.parent),
        "commit": prepared.commit, "render": prepared.project.render, "run_root": str(run_root),
        "output_directory": str(run_root / "output"), "job_path": str(job_folder / "job.json"),
        "receipt_path": str(run_root / "preparation-result.json"),
    }
    request_path = run_root / "request.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    script = repository / "unreal/prepare_project_job.py"
    command = [str(prepared.engine), str(prepared.uproject), "-run=pythonscript",
               f"-script={script.as_posix()}", "-EnablePlugins=RenderWorkerRuntime", "-unattended",
               "-NullRHI", "-NoSplash", "-NoSound", "-NoP4", f"-abslog={run_root / 'prepare-unreal.log'}"]
    progress(f"Reading {shot}'s sequence and render graph in Unreal")
    environment = dict(os.environ, RENDER_WORKER_JOB_REQUEST=str(request_path))
    with (run_root / "prepare-stdout.log").open("wb") as log:
        process = subprocess.Popen(command, cwd=prepared.checkout, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        started = time.monotonic()
        next_update = started + 30
        try:
            while process.poll() is None:
                if cancelled() or time.monotonic() - started > 1800:
                    raise PreparationCancelled("Unreal shot preparation cancelled or timed out")
                if time.monotonic() >= next_update:
                    progress(f"Unreal is preparing the shot ({int(time.monotonic() - started)} seconds); log: {run_root / 'prepare-unreal.log'}")
                    next_update = time.monotonic() + 30
                time.sleep(0.25)
        except BaseException:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                process.terminate()
            process.wait(timeout=30)
            raise
    receipt_path = Path(request["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    if receipt.get("success") is not True or receipt.get("job_id") != request["job_id"]:
        raise RuntimeError(f"Unreal could not prepare the shot; see {run_root / 'prepare-unreal.log'}\n{receipt.get('error', '')}")
    job = json.loads(Path(request["job_path"]).read_text(encoding="utf-8"))
    progress(f"Rendering {shot}: {job['frame_count']} frames into {run_root / 'output'}")
    render_started = time.monotonic()
    next_render_update = render_started + 30
    def check_render_cancelled():
        nonlocal next_render_update
        if time.monotonic() >= next_render_update:
            progress(f"Rendering {shot} ({int(time.monotonic() - render_started)} seconds); logs: {job_folder}")
            next_render_update = time.monotonic() + 30
        return cancelled()
    result = execute_unreal_job(job_folder, job, unreal_editor_cmd=prepared.engine,
                                local_uproject=prepared.uproject, render_farm_root=run_root / "renderFarm",
                                timeout_seconds=timeout_seconds, should_cancel=check_render_cancelled)
    summary = {"success": result.success, "project_id": prepared.project.project_id, "shot": shot,
               "commit": prepared.commit, "run_root": str(run_root), "reason": result.reason,
               "render": result.terminal_result_details()}
    (run_root / "result.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
