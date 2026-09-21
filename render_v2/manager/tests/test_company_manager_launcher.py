import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "tools/manager_v2_company.py"
spec = importlib.util.spec_from_file_location("manager_v2_company", path)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class CompanyManagerLauncherTests(unittest.TestCase):
    def test_missing_profile_writes_a_report_and_actionable_log_without_opening_gui(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"LOCALAPPDATA": temporary}):
            report = Path(temporary) / "report.json"
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                code = launcher.main(["--self-test", str(report)])
            self.assertEqual(1, code)
            self.assertFalse(json.loads(report.read_text())["success"])
            self.assertIn("company-manager.json", errors.getvalue())
            self.assertIn("--profile", errors.getvalue())
            self.assertTrue((launcher.data_directory() / "logs/manager.log").is_file())

    def test_worker_profile_is_rejected_with_manager_guidance(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "wrong-role.json"
            profile.write_text(json.dumps({"api_url": "https://v2.example.test", "worker_token": "test"}))
            with self.assertRaisesRegex(ValueError, "manager profile"):
                launcher.configure_company_environment(profile)

    def test_v1_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "wrong-service.json"
            profile.write_text(json.dumps({"api_url": "https://defect-farm-api.twilight-tooth-7b7c.workers.dev", "manager_token": "test"}))
            with self.assertRaisesRegex(Exception, "V1 production"):
                launcher.configure_company_environment(profile)

    def test_settings_are_per_user_and_existing_preferences_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"LOCALAPPDATA": temporary}):
            path = launcher.data_directory() / "manager.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"sentinel": true}')
            self.assertEqual(path, launcher.manager_settings_path())
            self.assertEqual('{"sentinel": true}', path.read_text())

    def test_company_profile_overrides_inherited_local_service(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {"DEFECT_FARM_API_URL": "http://127.0.0.1:8795"}):
            profile = Path(temporary) / "manager.json"
            profile.write_text(json.dumps({"api_url": "https://v2.example.test", "manager_token": "test-manager"}))
            connection = launcher.configure_company_environment(profile)
            self.assertEqual("https://v2.example.test", os.environ["DEFECT_FARM_API_URL"])
            self.assertEqual("manager", connection.role)
            self.assertEqual("test-manager", os.environ["DEFECT_FARM_MANAGER_TOKEN"])

    def test_missing_profile_does_not_start_the_manager_or_fall_back(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(FileNotFoundError):
                launcher.configure_company_environment(Path(temporary) / "missing.json")
            self.assertNotIn("DEFECT_FARM_API_URL", os.environ)
