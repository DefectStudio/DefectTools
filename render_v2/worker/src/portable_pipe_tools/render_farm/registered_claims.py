"""Worker-initiated queue claiming for explicitly registered local shows."""

from pathlib import Path

from portable_pipe_tools.render_farm.project_render import install_runtime
from portable_pipe_tools.render_farm.project_workspace import project_lock, PreparationError, PreparationCancelled
from portable_pipe_tools.render_farm.registered_sync import sync_registered_project, SYNC_POLICY
from portable_pipe_tools.render_farm.registered_render import local_project_lock, prepare_registered_job
from portable_pipe_tools.render_farm.queue import read_json_object, safe_name
from portable_pipe_tools.render_farm.unreal_runner import execute_unreal_job, UnrealExecutionResult
from portable_pipe_tools.render_farm.v2_gui_settings import load_registered_projects
from portable_pipe_tools.render_farm.worker import run_once


class RegisteredQueueWorker:
    def __init__(self, settings_path: Path, worker_name: str, *, dispatcher_client=None,
                 progress=print, executor=None):
        self.settings_path = Path(settings_path)
        self.worker_name = worker_name
        self.dispatcher = dispatcher_client
        if self.dispatcher is None:
            raise ValueError("V2 requires the company SQL dispatcher; filesystem job claiming is not supported.")
        self.progress = progress
        self.executor = executor or execute_unreal_job
        self.spool = self.settings_path.parent / "queue-spool" / safe_name(worker_name, "WORKER")
        self.projects = self.ready_projects()
        if not self.projects:
            raise ValueError("Register at least one available local project before starting the worker.")

    def ready_projects(self):
        engine = read_json_object(self.settings_path).get("unreal_editor_cmd", "")
        if not isinstance(engine, str) or not Path(engine).is_absolute() or not Path(engine).is_file():
            raise ValueError("Choose an existing UnrealEditor-Cmd.exe before starting the worker.")
        if Path(engine).name.casefold() != "unrealeditor-cmd.exe":
            raise ValueError("The engine setting must point to UnrealEditor-Cmd.exe.")
        ready = []
        for project in load_registered_projects(self.settings_path):
            farm = Path(project.render_farm_root)
            try:
                if not farm.is_dir() or farm.parent.name.casefold() != project.project_id.casefold():
                    raise ValueError("Dropbox show/renderFarm folder unavailable or mismatched")
                read_json_object(Path(project.local_uproject))
            except (OSError, ValueError) as error:
                self.progress(f"Skipping unavailable registration {project.project_id}: {error}")
                continue
            ready.append(project)
        return ready

    def _render(self, *, claimed_folder, job, should_cancel=lambda: False, timeout_seconds=7200, **_):
        identity = str(job.get("project_id") or job.get("project") or "")
        project, uproject, engine, _ = prepare_registered_job(self.settings_path, identity, Path(claimed_folder) / "job.json")
        try:
            with project_lock(local_project_lock(uproject)):
                if should_cancel():
                    return UnrealExecutionResult(False, "Stopped before Unreal launch", None, cancelled=True)
                commit = sync_registered_project(uproject, Path(claimed_folder) / "project-sync",
                                                 progress=self.progress, cancelled=should_cancel)
                install_runtime(uproject.parent, project_directory=uproject.parent)
                job.update(uproject=str(uproject), project=project.project_id, project_id=project.project_id,
                           worker_runtime_version=2, disable_project_scripts=False,
                           worker_sync_policy=SYNC_POLICY, prepared_git_commit=commit, git_commit_after_pull=commit)
                self.progress(f"Rendering claimed job {job['job_id']} using updated {uproject}")
                return self.executor(claimed_folder=claimed_folder, job=job, unreal_editor_cmd=engine,
                                     local_uproject=uproject, render_farm_root=Path(project.render_farm_root),
                                     should_cancel=should_cancel, timeout_seconds=timeout_seconds)
        except PreparationError as error:
            return UnrealExecutionResult(False, str(error), None, cancelled=isinstance(error, PreparationCancelled))

    def run_next(self, *, stopped=lambda: False, stage_callback=None, job_callback=None,
                 render_timeout_seconds=7200, heartbeat_interval_seconds=60):
        if stopped():
            return None
        projects = self.ready_projects()
        if not projects:
            self.progress("No registered local projects are currently available; no jobs claimed.")
            return run_once(farm_root=self.projects[0].render_farm_root, worker_name=self.worker_name,
                            simulate_success=False, minimum_stage_seconds=0, dispatcher_client=self.dispatcher,
                            cloud_spool_root=self.spool, eligible_project_ids=[],
                            dispatcher_capabilities={"registered_projects": []},
                            should_stop_before_claim=stopped)
        by_id = {p.project_id.casefold(): p for p in projects}
        def resolve_paths(job):
            project = by_id[str(job.get("project_id") or job.get("project") or "").casefold()]
            if not Path(project.local_uproject).is_file() or not Path(project.render_farm_root).is_dir():
                raise ValueError("Registered project disappeared before claim preparation")
            return Path(project.render_farm_root), Path(project.local_uproject)
        options = dict(worker_name=self.worker_name, simulate_success=False, render_with_unreal=True,
                       minimum_stage_seconds=0, unreal_runner=self._render, git_sync=None,
                       should_stop_before_claim=stopped, should_cancel_render=stopped,
                       stage_callback=stage_callback, job_callback=job_callback,
                       render_timeout_seconds=render_timeout_seconds)
        return run_once(farm_root=projects[0].render_farm_root, dispatcher_client=self.dispatcher,
                        dispatcher_app_version="render-worker-v2-registered",
                        dispatcher_capabilities={"registered_projects": [p.project_id for p in projects],
                                                 "sync_policy": SYNC_POLICY},
                        eligible_project_ids=[p.project_id for p in projects], job_paths_resolver=resolve_paths,
                        cloud_spool_root=self.spool,
                        dispatcher_heartbeat_interval_seconds=heartbeat_interval_seconds, **options)
