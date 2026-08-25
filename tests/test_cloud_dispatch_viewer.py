from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.cloud_dispatch import (
    load_dispatcher_connection,
)


class BuiltInViewerConnectionTests(unittest.TestCase):
    def test_viewer_connection_ships_without_local_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_settings = Path(temporary_directory) / "missing.json"
            with patch.dict(
                os.environ,
                {
                    "DEFECT_FARM_API_URL": "",
                    "DEFECT_FARM_VIEWER_TOKEN": "",
                },
            ):
                connection = load_dispatcher_connection(
                    "viewer",
                    settings_path=missing_settings,
                    required=True,
                )

        self.assertIsNotNone(connection)
        assert connection is not None
        self.assertEqual("viewer", connection.role)
        self.assertEqual(
            "https://defect-farm-api.twilight-tooth-7b7c.workers.dev",
            connection.api_url,
        )
        self.assertTrue(connection.token)


if __name__ == "__main__":
    unittest.main()
