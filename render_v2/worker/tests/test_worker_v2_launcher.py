import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.worker import WorkerResult


class WorkerLauncherTests(unittest.TestCase):
    def test_explicit_claim_command_uses_current_registered_worker_interface(self):
        path = Path(__file__).resolve().parents[1] / "src/portable_pipe_tools/apps/worker_v2_launcher.py"
        spec = importlib.util.spec_from_file_location("v2_entry_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        class Service:
            def run_next(self, *, render_timeout_seconds):
                self.timeout = render_timeout_seconds
                return WorkerResult("complete", Path("completed-job"), "Test completed")
        service = Service()
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "result.json"
            with patch.object(module, "RegisteredQueueWorker", return_value=service), \
                 patch.object(module, "load_dispatcher_connection") as connection:
                code = module.claim_once(["--worker", "Test", "--timeout", "90", "--report", str(report)])
            self.assertEqual(0, code)
            self.assertEqual(90, service.timeout)
            self.assertTrue(json.loads(report.read_text())["success"])
            connection.assert_not_called()
