from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.render_farm.project_registration import ProjectRegistration
from portable_pipe_tools.render_farm.v2_gui_settings import save_registered_projects, save_unreal_editor_preference
from portable_pipe_tools.render_farm.worker_setup import check_worker_setup


class WorkerSetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.settings = self.root / "worker.json"
        self.project = self.root / "local/Show.uproject"
        self.project.parent.mkdir()
        self.project.write_text('{"EngineAssociation":"5.8"}')
        self.farm = self.root / "Dropbox/Show/renderFarm"
        self.farm.mkdir(parents=True)
        self.engine = self.root / "UE/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
        self.engine.parent.mkdir(parents=True)
        self.engine.write_bytes(b"fixture")
        save_unreal_editor_preference(str(self.engine), self.settings)
        save_registered_projects([ProjectRegistration.from_dict(dict(project_id="Show", name="Show",
            local_uproject=str(self.project), render_farm_root=str(self.farm)))], self.settings)

    def test_checks_local_paths_and_auth_without_claiming_or_installing(self):
        dispatcher = Mock()
        dispatcher.check_auth.return_value = "worker"
        report = check_worker_setup(self.settings, dispatcher=dispatcher)
        self.assertTrue(report.ok, report.describe())
        self.assertEqual(["Show"], report.projects)
        self.assertEqual([unittest.mock.call.check_auth()], dispatcher.mock_calls)
        self.assertEqual([], list(self.farm.iterdir()))
        self.assertFalse((self.project.parent / "Plugins").exists())

    def test_missing_paths_and_wrong_credential_are_actionable(self):
        self.engine.unlink()
        self.project.unlink()
        dispatcher = Mock()
        dispatcher.check_auth.return_value = "manager"
        report = check_worker_setup(self.settings, dispatcher=dispatcher)
        self.assertFalse(report.ok)
        self.assertIn("UnrealEditor-Cmd.exe", report.describe())
        self.assertIn("Show:", report.describe())
        self.assertIn("worker credential", report.describe())

    def test_engine_version_mismatch_and_unwritable_folder(self):
        version = self.engine.parents[2] / "Build/Build.version"
        version.parent.mkdir()
        version.write_text('{"MajorVersion":5,"MinorVersion":7}')
        self.assertIn("requires Unreal 5.8", check_worker_setup(self.settings).describe())
        version.write_text('{"MajorVersion":5,"MinorVersion":8}')
        with patch("portable_pipe_tools.render_farm.worker_setup._check_writable", side_effect=PermissionError("read only")):
            self.assertIn("read only", check_worker_setup(self.settings).describe())

    def test_unmanaged_plugin_is_preserved(self):
        plugin = self.project.parent / "Plugins/RenderWorkerRuntime"
        plugin.mkdir(parents=True)
        self.assertIn("unmanaged", check_worker_setup(self.settings).describe())
        self.assertEqual([], list(plugin.iterdir()))
