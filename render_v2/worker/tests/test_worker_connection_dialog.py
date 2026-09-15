from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock

from portable_pipe_tools.apps.worker_connection_dialog import WorkerConnectionDialog
from portable_pipe_tools.render_farm.cloud_dispatch import load_cloud_settings
from portable_pipe_tools.render_farm.cloud_dispatch import DispatcherConnection, DispatcherConfigurationError


class WorkerConnectionTests(unittest.TestCase):
    def test_http_loopback_exception_does_not_allow_remote_hosts(self):
        for url in ("http://localhost.example.com", "http://127.0.0.1.example.com", "https://user:password@example.com"):
            with self.subTest(url=url), self.assertRaises(DispatcherConfigurationError):
                DispatcherConnection(url, "worker", "synthetic-token")

    def test_fresh_connection_is_blank_and_saves_only_worker_credential(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "connection.json"
            root = tk.Tk()
            root.withdraw()
            try:
                saved = Mock()
                dialog = WorkerConnectionDialog(root, on_save=saved, settings_path=path)
                self.assertEqual("", dialog.url.get())
                self.assertEqual("", dialog.token.get())
                dialog.save()
                self.assertTrue(dialog.error.get())
                self.assertFalse(path.exists())
                dialog.url.set("https://v2.example.com")
                dialog.token.set("synthetic-worker-token")
                dialog.save()
                self.assertEqual("synthetic-worker-token", load_cloud_settings(path)["worker_token"])
                self.assertNotIn("manager_token", load_cloud_settings(path))
                saved.assert_called_once_with()
                reopened = WorkerConnectionDialog(root, on_save=saved, settings_path=path)
                self.assertEqual("https://v2.example.com", reopened.url.get())
            finally:
                root.destroy()
