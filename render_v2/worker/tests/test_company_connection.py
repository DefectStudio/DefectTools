import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.company_connection import load_company_worker_connection
from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherConfigurationError

MODULE = "portable_pipe_tools.render_farm.company_connection"


class CompanyConnectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(patch(MODULE + ".is_frozen", return_value=True))
        self.enterContext(patch(MODULE + ".resource_root", return_value=self.root))

    def write_profile(self, **values):
        (self.root / "worker_company_connection.json").write_text(json.dumps(values))

    def test_packaged_worker_uses_bundled_worker_profile_without_machine_setup(self):
        self.write_profile(api_url="https://v2.example.test", worker_token="worker-test-only")
        with patch(MODULE + ".load_dispatcher_connection", side_effect=AssertionError("No machine setup")):
            connection = load_company_worker_connection()
        self.assertEqual("https://v2.example.test", connection.api_url)
        self.assertEqual("worker", connection.role)

    def test_missing_profile_is_an_error_not_a_machine_or_filesystem_fallback(self):
        with patch(MODULE + ".load_dispatcher_connection", side_effect=AssertionError("No fallback")):
            with self.assertRaisesRegex(DispatcherConfigurationError, "configured build"):
                load_company_worker_connection()

    def test_bundled_profile_cannot_target_v1_production(self):
        self.write_profile(api_url="https://defect-farm-api.twilight-tooth-7b7c.workers.dev", worker_token="test")
        with self.assertRaisesRegex(DispatcherConfigurationError, "V1 production"):
            load_company_worker_connection()

    def test_source_checkout_can_use_its_development_service(self):
        with patch(MODULE + ".is_frozen", return_value=False), patch(MODULE + ".load_dispatcher_connection") as load:
            self.assertIs(load.return_value, load_company_worker_connection())
            load.assert_called_once_with("worker", required=True)
