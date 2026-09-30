"""Python V2 GUI and explicit diagnostic commands; no automatic work on launch."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import traceback

from portable_pipe_tools.app_runtime import default_settings_path, is_frozen, migrate_legacy_source_settings, prepare_external_programs, resource_root, settings_directory
from portable_pipe_tools.apps.render_worker_v2_app import RenderWorkerV2App
from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherClient, load_dispatcher_connection
from portable_pipe_tools.render_farm.registered_claims import RegisteredQueueWorker
from portable_pipe_tools.render_farm.company_connection import load_company_worker_connection
from portable_pipe_tools.render_farm.worker_setup import check_worker_setup
from portable_pipe_tools.render_farm.registered_render import main as render_main
from portable_pipe_tools.render_farm.v2_gui_settings import save_unreal_editor_preference, save_dropbox_root
from tkinter import messagebox

VERSION = "2.0.0-preview.1"


class LogStream:
    def write(self, text):
        if text.strip():
            logging.info(text.rstrip())
        return len(text)

    def flush(self):
        for handler in logging.getLogger().handlers:
            handler.flush()


def self_test(report_path: Path) -> int:
    """Synthetic temporary registrations; never connects, claims, or renders."""
    report = dict(success=False, version=VERSION, frozen=is_frozen(), executable=sys.executable,
                  settings_path=str(default_settings_path()), python_version=sys.version,
                  git_available=shutil.which("git") is not None)
    app = None
    original_local = os.environ.get("LOCALAPPDATA")
    try:
        report["company_service_url"] = load_company_worker_connection().api_url
        report["coordination"] = "sql"
        required = ["unreal/RenderWorkerRuntime/RenderWorkerRuntime.uplugin",
                    "unreal/RenderWorkerRuntime/Content/Python/init_unreal.py",
                    "unreal/RenderWorkerRuntime/Content/Python/render_worker_runtime_executor.py"]
        for name in required:
            path = resource_root() / name
            if not path.is_file():
                raise RuntimeError(f"Missing bundled resource: {name}")
            if path.suffix == ".py":
                compile(path.read_text(encoding="utf-8"), name, "exec")
        report["resources"] = required
        with tempfile.TemporaryDirectory(prefix="worker-v2-selftest-") as temporary:
            base = Path(temporary)
            os.environ["LOCALAPPDATA"] = str(base / "user-data")
            settings = base / "settings/worker_v2.json"
            save_unreal_editor_preference("", settings)
            engine = base / "UnrealEditor-Cmd.exe"
            engine.touch()
            show = base / "Dropbox/Test Show"
            show.mkdir(parents=True)
            project = base / "Local Project/Test.uproject"
            project.parent.mkdir()
            project.write_text("{}", encoding="utf-8")
            save_dropbox_root(str(show.parent), settings)
            for launch in range(2):
                app = RenderWorkerV2App(settings_path=settings)
                app.root.withdraw()
                app.root.update_idletasks()
                if app._listener_state.active or app._busy:
                    raise RuntimeError("Startup unexpectedly started work")
                if launch == 0:
                    if app.project_list.projects_frame.winfo_manager():
                        raise RuntimeError("Project list appeared before selecting an engine")
                    if not app.engine_setup_frame.winfo_manager():
                        raise RuntimeError("Engine selection is hidden after Dropbox setup")
                    app.unreal_editor_cmd_var.set(str(engine))
                    app._save_engine_field()
                    if not app.project_list.projects_frame.winfo_manager():
                        raise RuntimeError("Engine selection did not reveal the project list")
                    if app.project_list.projects:
                        raise RuntimeError("Fresh configuration included registrations")
                    app.project_list.add()
                    dialog = app.project_list.dialog
                    dialog.fields["project_id"].set("Test Show")
                    dialog._select_show()
                    dialog.fields["local_uproject"].set(str(project))
                    dialog.save()
                    if not app.project_list.projects:
                        raise RuntimeError("GUI registration could not be saved")
                    app.worker_name_var.set("Portable-Test-Worker")
                    app._save_worker_preferences()
                else:
                    if [p.project_id for p in app.project_list.projects] != ["Test Show"]:
                        raise RuntimeError("Registrations did not survive restart")
                    if (app.worker_name_var.get() != "Portable-Test-Worker"
                            or app.unreal_editor_cmd_var.get() != str(engine)):
                        raise RuntimeError("Worker preferences did not survive restart")
                    if app.project_list.projects[0].allow_downloads:
                        raise RuntimeError("Downloads should be off by default")
                if not app._animation_frames:
                    raise RuntimeError("Bundled GUI animation resources are unavailable")
                report["tk_version"] = str(app.root.tk.call("info", "patchlevel"))
                report["gui_class"] = type(app).__name__
                app._shutdown_application(0)
                app = None
            if (show / "renderFarm").exists():
                raise RuntimeError("Registration unexpectedly created a shared queue")
            report["settings_reload"] = True
            report["automatic_work_started"] = False
        command = [os.environ.get("COMSPEC", "C:/Windows/System32/cmd.exe"), "/d", "/c", "echo worker-v2-child-ok"]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode or "worker-v2-child-ok" not in result.stdout:
            raise RuntimeError("External process startup failed")
        report["external_process"] = True
        report["success"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if app is not None:
            app._shutdown_application(1)
        if original_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = original_local
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1


def check_setup(argv):
    parser = argparse.ArgumentParser(description="Check local projects and company SQL access without claiming jobs.")
    parser.add_argument("--settings", type=Path, default=default_settings_path())
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {"success": False, "version": VERSION, "coordination": "sql"}
    try:
        connection = load_company_worker_connection()
        checked = check_worker_setup(args.settings, dispatcher=DispatcherClient(connection))
        report.update(asdict(checked), success=checked.ok, company_service_url=connection.api_url)
    except Exception as error:
        report["errors"] = [str(error)]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1


def claim_once(argv):
    parser = argparse.ArgumentParser(description="Claim and render at most one job from registered projects.")
    parser.add_argument("--settings", type=Path, default=default_settings_path())
    parser.add_argument("--worker", required=True)
    parser.add_argument("--cloud", action="store_true", help=argparse.SUPPRESS)  # Legacy spelling; SQL is always required.
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=7200)
    args = parser.parse_args(argv)
    report = {"success": False, "version": VERSION}
    try:
        dispatcher = DispatcherClient(load_company_worker_connection())
        service = RegisteredQueueWorker(args.settings, args.worker, dispatcher_client=dispatcher, progress=logging.info)
        result = service.run_next(render_timeout_seconds=args.timeout)
        report.update(success=result is not None and result.status == "complete",
                      result=asdict(result) if result is not None else None)
    except Exception:
        report["error"] = traceback.format_exc()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return 0 if report["success"] else 1


def main(argv=None):
    multiprocessing.freeze_support()
    argv = list(sys.argv[1:] if argv is None else argv)
    logs = settings_directory() / "logs"
    try:
        if not argv:
            migrate_legacy_source_settings()
        logs.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                            handlers=[RotatingFileHandler(logs / "worker.log", maxBytes=3_000_000,
                                                          backupCount=2, encoding="utf-8")])
        if sys.stdout is None:
            sys.stdout = LogStream()
        if sys.stderr is None:
            sys.stderr = LogStream()
        prepare_external_programs()
        if len(argv) == 2 and argv[0] == "--self-test":
            return self_test(Path(argv[1]))
        if argv and argv[0] == "render":
            return render_main(argv[1:])
        if argv and argv[0] == "claim-once":
            return claim_once(argv[1:])
        if argv and argv[0] == "check-setup":
            return check_setup(argv[1:])
        if argv:
            raise ValueError("Supported commands: --self-test REPORT, check-setup, render, claim-once; omit arguments to open the GUI.")
        logging.info("Starting Render Worker V2 %s", VERSION)
        return RenderWorkerV2App().run()
    except Exception as error:
        logging.exception("Render Worker V2 failed")
        if not argv:
            messagebox.showerror("Render Worker V2", f"The worker could not start: {error}\nDetails: {logs / 'worker.log'}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
