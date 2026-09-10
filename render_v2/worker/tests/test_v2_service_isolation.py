import unittest
from unittest.mock import patch
from pathlib import Path
from portable_pipe_tools.render_farm.cloud_dispatch import get_default_cloud_settings_path
from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherConnection, DispatcherConfigurationError


class V2ServiceIsolationTests(unittest.TestCase):
    def test_credentials_are_separate_from_v1(self):
        with patch.dict("os.environ", {"LOCALAPPDATA": "C:/LocalTest"}):
            path = get_default_cloud_settings_path()
        self.assertEqual(Path("C:/LocalTest/DefectStudio/RenderFarmV2"), path.parent)

    def test_v1_service_is_rejected_for_every_role(self):
        for role in ("manager", "worker", "viewer", "submit"):
            with self.subTest(role=role), self.assertRaises(DispatcherConfigurationError):
                DispatcherConnection("https://defect-farm-api.twilight-tooth-7b7c.workers.dev", role, "test")

    def test_separate_local_service_is_allowed(self):
        self.assertEqual("http://127.0.0.1:8795", DispatcherConnection("http://127.0.0.1:8795", "worker", "test").api_url)
