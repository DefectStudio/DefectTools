from __future__ import annotations

import logging
from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from portable_pipe_tools.apps.render_worker_app import (
    AUTOMATIC_START_DELAY_MS,
    DEFAULT_RENDER_TIMEOUT_HOURS,
    QueueLogHandler,
    RenderWorkerApp,
    format_render_timeout_hours,
    format_job_activity,
    parse_render_timeout_hours,
)


class QueueLogHandlerTests(unittest.TestCase):
    def test_log_records_are_forwarded_to_the_ui_queue(self) -> None:
        output_queue: Queue[str] = Queue()
        handler = QueueLogHandler(output_queue)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        record = logging.LogRecord(
            name="render_worker",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Claimed test job",
            args=(),
            exc_info=None,
        )

        handler.emit(record)

        self.assertEqual("INFO: Claimed test job", output_queue.get_nowait())


class RenderWorkerAppTests(unittest.TestCase):
    def test_successful_startup_update_schedules_automatic_worker_start(self) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._startup_update_complete = False
        app._closing = False
        app._automatic_start_after_id = None
        app._worker_git_branch = ""
        app._worker_git_commit = ""
        app.root = Mock()
        app.root.after.return_value = "after-auto-start"
        app.status_var = Mock()
        app._log = Mock()
        app._refresh_control_states = Mock()
        result = SimpleNamespace(
            update_installed=False,
            git_pull=SimpleNamespace(
                branch="main",
                commit_before="a" * 40,
                commit_after="a" * 40,
            ),
        )

        app._startup_update_succeeded(result)

        self.assertTrue(app._startup_update_complete)
        self.assertEqual("after-auto-start", app._automatic_start_after_id)
        app.root.after.assert_called_once_with(
            AUTOMATIC_START_DELAY_MS,
            app._automatic_start_worker,
        )

    def test_automatic_start_skips_the_manual_confirmation(self) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._automatic_start_after_id = "after-auto-start"
        app._closing = False
        app._start_worker = Mock()

        app._automatic_start_worker()

        self.assertIsNone(app._automatic_start_after_id)
        app._start_worker.assert_called_once_with(require_confirmation=False)

    def test_automatic_start_does_not_run_while_closing(self) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._automatic_start_after_id = "after-auto-start"
        app._closing = True
        app._start_worker = Mock()

        app._automatic_start_worker()

        self.assertIsNone(app._automatic_start_after_id)
        app._start_worker.assert_not_called()

    def test_render_timeout_defaults_to_two_hours(self) -> None:
        self.assertEqual(2.0, DEFAULT_RENDER_TIMEOUT_HOURS)
        self.assertEqual(2.0, parse_render_timeout_hours("2"))
        self.assertEqual(0.25, parse_render_timeout_hours("0.25"))
        self.assertEqual("1 hour", format_render_timeout_hours(1.0))
        self.assertEqual("2 hours", format_render_timeout_hours(2.0))

    def test_render_timeout_rejects_invalid_hours(self) -> None:
        for value in ("", "zero", "0", "0.1", "24.1", "nan"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_render_timeout_hours(value)

    def test_job_activity_uses_short_graph_name_and_padded_version(self) -> None:
        activity = format_job_activity(
            {
                "shot_name": "BSH_000_0030",
                "render_version": 10,
                "render_config": (
                    "/Game/_S3Bishop/RenderSettings/beauty_LowHDsRGB."
                    "beauty_LowHDsRGB"
                ),
            }
        )

        self.assertEqual(
            "Shot: BSH_000_0030  —  Version: v010  —  "
            "Render Setting: beauty_LowHDsRGB",
            activity,
        )

    def test_job_activity_preserves_an_existing_version_prefix(self) -> None:
        activity = format_job_activity(
            {
                "shot_name": "SH010",
                "render_version": "v002",
                "render_config": "/Game/Render/Hero.Hero",
            }
        )

        self.assertIn("Version: v002", activity)


if __name__ == "__main__":
    unittest.main()
