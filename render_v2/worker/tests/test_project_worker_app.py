import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest

from portable_pipe_tools.apps.project_worker_app import ProjectWorkerApp


class ProjectWorkerAppTests(unittest.TestCase):
    def test_window_loads_catalog_without_a_project_checkout_or_farm_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            catalog = folder / "projects.json"
            catalog.write_text(json.dumps({"schema_version": 1, "projects": [{
                "project_id": "sample", "repository": str(folder / "not-cloned"),
                "branch": "main", "uproject": "Sample.uproject", "lfs": False,
            }]}))
            settings = folder / "settings.json"
            settings.write_text(json.dumps({"catalog": str(catalog), "workspace_root": str(folder / "workspace")}))
            root = tk.Tk()
            root.withdraw()
            app = ProjectWorkerApp(root, settings_path=settings)
            try:
                deadline = time.monotonic() + 5
                while app.busy and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.02)
                self.assertFalse(app.busy)
                self.assertEqual("sample", app.project.get())
                self.assertEqual("normal", str(app.render_button['state']))
                self.assertFalse((folder / "workspace").exists())
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
