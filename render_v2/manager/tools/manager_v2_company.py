"""Launch Manager V2 against the administrator-provisioned company SQL service."""

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import sys
import tempfile

from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherConnection


def default_profile_path():
    return (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        / "DefectStudio/RenderFarmV2/company-manager.json"
    )


def data_directory():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "DefectStudio/RenderFarmManagerV2"


def configure_company_environment(profile_path=None):
    profile_path = profile_path or default_profile_path()
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8-sig"))
    if not isinstance(profile, dict) or not profile.get("api_url") or not profile.get("manager_token"):
        raise ValueError("The V2 manager profile must contain api_url and manager_token; use the manager profile, not the worker or submitter profile.")
    connection = DispatcherConnection(profile["api_url"], "manager", profile["manager_token"])
    os.environ["DEFECT_FARM_API_URL"] = connection.api_url
    os.environ["DEFECT_FARM_MANAGER_TOKEN"] = connection.token
    return connection


def manager_settings_path():
    settings = data_directory() / "manager.json"
    legacy = Path(__file__).resolve().parents[1] / "LocalSaveFiles/project-registry-validation/manager-demo.json"
    if not settings.exists() and legacy.is_file():
        settings.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, settings)
    return settings


def self_test(connection):
    """Check hosted read access and build the real GUI without changing any jobs."""
    from portable_pipe_tools.apps.farm_render_manager_app import FarmRenderManagerApp
    from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherClient
    from portable_pipe_tools.render_farm.manager_settings import save_auto_refresh_enabled
    client = DispatcherClient(connection)
    health = client.health()
    if health.get("service") != "defect-farm-api-v2" or health.get("database") != "connected":
        raise RuntimeError("The company V2 database did not pass its health check.")
    if client.check_auth() != "manager":
        raise RuntimeError("This profile does not have the manager role.")
    client.list_jobs()
    client.list_workers()
    with tempfile.TemporaryDirectory(prefix="manager-v2-selftest-") as temporary:
        settings = Path(temporary) / "manager.json"
        save_auto_refresh_enabled(False, settings)
        app = FarmRenderManagerApp(settings_path=settings, prompt_on_startup=False)
        try:
            app.root.title("Farm Render Manager V2 — Startup Check")
            app.root.update_idletasks()
            app.root.update()
        finally:
            app._on_close()
    return {"success": True, "database": "connected", "role": "manager", "gui": True,
            "jobs_read": True, "workers_read": True, "jobs_modified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, help="Administrator-provided V2 manager profile")
    parser.add_argument("--self-test", type=Path, metavar="REPORT", help="Check SQL read access and GUI startup, then exit")
    args = parser.parse_args(argv)
    log_path = data_directory() / "logs/manager.log"
    report = {"success": False}
    log_handler = None
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_handler = RotatingFileHandler(log_path, maxBytes=3_000_000, backupCount=2, encoding="utf-8")
        log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(log_handler)
        logging.getLogger().setLevel(logging.INFO)
        profile_path = args.profile or default_profile_path()
        if not profile_path.is_file():
            raise RuntimeError(
                f"The V2 manager credential file is missing: {profile_path}\n"
                "Ask the administrator for the company-manager.json profile and place it at that path, "
                "or launch with --profile PATH. The worker/submitter profile cannot manage jobs."
            )
        connection = configure_company_environment(profile_path)
        if args.self_test:
            report = self_test(connection)
        else:
            from portable_pipe_tools.apps.farm_render_manager_app import FarmRenderManagerApp
            app = FarmRenderManagerApp(settings_path=manager_settings_path(), prompt_on_startup=True)
            app.root.title("Farm Render Manager V2 — Company SQL")
            def callback_error(exc_type, exc, tb):
                logging.error("Manager UI action failed", exc_info=(exc_type, exc, tb))
                print(f"Manager UI action failed: {exc}\nLog: {log_path}", file=sys.stderr)
            app.root.report_callback_exception = callback_error
            app.root.mainloop()
        return 0
    except Exception as error:
        logging.exception("Manager V2 failed to start")
        print(f"Render Farm Manager V2 could not start: {error}\nLog: {log_path}", file=sys.stderr)
        report["error"] = str(error)
        return 1
    finally:
        if log_handler is not None:
            logging.getLogger().removeHandler(log_handler)
            log_handler.close()
        if args.self_test:
            args.self_test.parent.mkdir(parents=True, exist_ok=True)
            args.self_test.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
