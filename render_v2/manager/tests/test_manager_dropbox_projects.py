from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from portable_pipe_tools.apps.farm_render_manager_app import FarmRenderManagerApp


class ManagerDropboxTests(unittest.TestCase):
    def test_empty_show_is_listed_without_registry_or_job_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Development/renderFarm").mkdir(parents=True)
            app = SimpleNamespace(repository_path=root, set_projects=Mock(),
                                  all_jobs=[], all_workers=[], dispatcher_client=Mock())
            FarmRenderManagerApp._update_project_choices(app)
            self.assertEqual(["Development"], list(app.set_projects.call_args.args[0]))
            app.dispatcher_client.assert_not_called()
            (root / "s3bishop").mkdir()
            FarmRenderManagerApp._update_project_choices(app)
            self.assertEqual(["Development", "s3bishop"], list(app.set_projects.call_args.args[0]))
            self.assertFalse((root / "s3bishop/renderFarm").exists())
