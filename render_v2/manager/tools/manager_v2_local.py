"""Open Manager V2 against its isolated localhost API and Dropbox folders.

The existing local-demo settings path is retained for preference continuity.
"""

import os
from pathlib import Path

from portable_pipe_tools.apps.farm_render_manager_app import FarmRenderManagerApp
from portable_pipe_tools.render_farm.manager_settings import save_auto_refresh_enabled


def main():
    os.environ["DEFECT_FARM_API_URL"] = "http://127.0.0.1:8795"
    for role in ("manager", "worker", "viewer", "submit"):
        os.environ[f"DEFECT_FARM_{role.upper()}_TOKEN"] = f"local-{role}-token-for-tests"
    settings = Path(__file__).resolve().parents[1] / "LocalSaveFiles/project-registry-validation/manager-demo.json"
    save_auto_refresh_enabled(False, settings)
    app = FarmRenderManagerApp(settings_path=settings, prompt_on_startup=True)
    app.root.title("Farm Render Manager V2 — Local")
    app.root.mainloop()


if __name__ == "__main__":
    main()
