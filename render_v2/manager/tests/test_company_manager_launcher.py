import importlib.util
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
