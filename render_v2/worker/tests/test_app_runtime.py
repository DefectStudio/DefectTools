import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.app_runtime import default_catalog_path, default_settings_path, resource_root


class AppRuntimeTests(unittest.TestCase):
    def test_cloud_control_files_use_v2_data_location(self):
        from portable_pipe_tools.render_farm.cloud_queue import get_default_cloud_spool_root
        with tempfile.TemporaryDirectory() as temporary, \
             patch.dict(os.environ, {"LOCALAPPDATA": temporary, "DEFECT_FARM_LOCAL_SPOOL_ROOT": ""}):
            self.assertTrue(get_default_cloud_spool_root("Test").is_relative_to(
                Path(temporary) / "DefectStudio/RenderFarmV2"))

    def test_source_launch_keeps_existing_repository_settings(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(resource_root() / "LocalSaveFiles/worker_v2.json", default_settings_path())
            self.assertTrue(default_catalog_path().is_file())

    def test_frozen_resources_and_persistent_settings_are_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "temporary-extraction"
            install = root / "portable-app"
            install.mkdir()
            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "_MEIPASS", str(bundle), create=True), \
                 patch.object(sys, "executable", str(install / "RenderWorker.exe")), \
                 patch.dict(os.environ, {"LOCALAPPDATA": str(root / "user-data")}):
                self.assertEqual(bundle, resource_root())
                self.assertEqual(root / "user-data/DefectStudio/RenderWorkerV2/worker_v2.json", default_settings_path())
                from portable_pipe_tools.render_farm.settings import get_default_settings_path
                self.assertEqual(default_settings_path().parent / "render_worker_local_save.json", get_default_settings_path())
                self.assertEqual(bundle / "projects.json", default_catalog_path())
                (install / "projects.json").write_text("{}")
                self.assertEqual(install / "projects.json", default_catalog_path())


if __name__ == "__main__":
    unittest.main()
