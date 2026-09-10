"""Windowed EXE entry point; optional CLI commands log to the user data folder."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

from portable_pipe_tools.app_runtime import (
    default_catalog_path, default_settings_path, is_frozen, prepare_external_programs,
    resource_root, settings_directory,
)
from portable_pipe_tools.apps.project_worker_app import ProjectWorkerApp, main as gui_main
from portable_pipe_tools.render_farm.project_worker import main as cli_main
import tkinter as tk
from tkinter import messagebox


class LogStream:
    def write(self, text):
        if text.strip():
            logging.info(text.rstrip())
        return len(text)

    def flush(self):
        for handler in logging.getLogger().handlers:
            handler.flush()


def self_test(report_path: Path) -> int:
    report = {"success": False, "frozen": is_frozen(), "executable": sys.executable,
              "settings_path": str(default_settings_path()), "python_version": sys.version}
    root = None
    app = None
    try:
        required = ["projects.json", "unreal/prepare_project_job.py",
                    "unreal/RenderWorkerRuntime/RenderWorkerRuntime.uplugin",
                    "unreal/RenderWorkerRuntime/Content/Python/init_unreal.py",
                    "unreal/RenderWorkerRuntime/Content/Python/render_worker_runtime_executor.py"]
        missing = [name for name in required if not (resource_root() / name).is_file()]
        if missing:
            raise RuntimeError(f"Missing packaged resources: {missing}")
        for name in required:
            if name.endswith(".py"):
                compile((resource_root() / name).read_text(encoding="utf-8"), name, "exec")
        report["resources"] = required
        report["catalog"] = str(default_catalog_path())
        with tempfile.TemporaryDirectory() as temporary:
            settings = Path(temporary) / "settings.json"
            for launch in range(2):
                root = tk.Tk()
                root.withdraw()
                app = ProjectWorkerApp(root, settings_path=settings)
                deadline = time.monotonic() + 15
                while app.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.02)
                if app.busy or not app.projects:
                    raise RuntimeError(f"GUI/catalog startup failed: {app.status.get()}")
                report["gui_projects"] = list(app.projects)
                report["tk_version"] = str(root.tk.call("info", "patchlevel"))
                if launch == 0:
                    # Exercise settings saving without running project preparation.
                    app.launch = lambda operation, callback: None
                    app.start_job(False)
                    saved = json.loads(settings.read_text(encoding="utf-8"))
                    if saved["catalog"] != "":
                        raise RuntimeError("Default catalog saved a temporary resource path")
                else:
                    report["settings_reload"] = app.catalog.get() == ""
                    if not report["settings_reload"]:
                        raise RuntimeError("Default catalog did not survive settings reload")
                app.close()
                app = root = None
        report["external_programs"] = {}
        for key, command in [("git", ["git", "--version"]), ("git_lfs", ["git", "lfs", "version"])]:
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=15,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                report["external_programs"][key] = {"available": result.returncode == 0,
                                                     "details": (result.stdout + result.stderr).strip()[:500]}
            except OSError as error:
                report["external_programs"][key] = {"available": False, "details": str(error)}
        report["success"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if app is not None:
            if app.busy:
                app.after_cancel(app.after_id)
                root.destroy()
            else:
                app.close()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["success"] else 1


def main(argv=None):
    multiprocessing.freeze_support()
    argv = list(sys.argv[1:] if argv is None else argv)
    logs = settings_directory() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[RotatingFileHandler(logs / "worker.log", maxBytes=3_000_000,
                                                      backupCount=2, encoding="utf-8")])
    if sys.stdout is None:
        sys.stdout = LogStream()
    if sys.stderr is None:
        sys.stderr = LogStream()
    # App/Tk imports above are complete; no bundled helper executable is launched.
    prepare_external_programs()
    try:
        if len(argv) == 2 and argv[0] == "--self-test":
            return self_test(Path(argv[1]))
        if argv:
            return cli_main(argv)
        gui_main()
        return 0
    except Exception:
        logging.exception("Render Worker failed")
        if not argv:
            messagebox.showerror("Render Worker", f"The worker could not start. Details: {logs / 'worker.log'}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
