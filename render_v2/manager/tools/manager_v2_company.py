"""Launch Manager V2 against the administrator-provisioned company SQL service."""

import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from portable_pipe_tools.apps.farm_render_manager_app import FarmRenderManagerApp
from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherConnection


def configure_company_environment(profile_path=None):
    profile_path = profile_path or (
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        / "DefectStudio/RenderFarmV2/company-manager.json"
    )
    profile = json.loads(Path(profile_path).read_text(encoding="utf-8-sig"))
    connection = DispatcherConnection(profile["api_url"], "manager", profile["manager_token"])
    os.environ["DEFECT_FARM_API_URL"] = connection.api_url
    os.environ["DEFECT_FARM_MANAGER_TOKEN"] = connection.token
    return connection


def main():
    try:
        configure_company_environment()
    except Exception:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Manager V2 company service", "The company V2 service profile is missing or invalid. Ask the administrator to provision this manager.", parent=root)
        root.destroy()
        return 1
    settings = Path(__file__).resolve().parents[1] / "LocalSaveFiles/project-registry-validation/manager-demo.json"
    app = FarmRenderManagerApp(settings_path=settings, prompt_on_startup=True)
    app.root.title("Farm Render Manager V2 — Company SQL")
    app.root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
