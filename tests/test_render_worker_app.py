from __future__ import annotations

import logging
from queue import Queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.apps.render_worker_app import (
    AUTOMATIC_START_DELAY_MS,
    DEFAULT_RENDER_TIMEOUT_HOURS,
    PERIODIC_UPDATE_INTERVAL_MS,
    QueueLogHandler,
    RenderWorkerApp,
    format_render_timeout_hours,
    format_job_activity,
    parse_render_timeout_hours,
)
from portable_pipe_tools.render_farm.worker import WorkerStage


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

    def test_active_worker_schedules_update_check_for_ten_minutes(self) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._closing = False
        app._restart_pending = False
        app._periodic_update_after_id = None
        app._listener_state = SimpleNamespace(active=True)
        app.root = Mock()
        app.root.after.return_value = "after-periodic-update"

        app._schedule_periodic_update_check()

        self.assertEqual("after-periodic-update", app._periodic_update_after_id)
        app.root.after.assert_called_once_with(
            PERIODIC_UPDATE_INTERVAL_MS,
            app._run_periodic_update_check,
        )

    def test_periodic_update_check_is_skipped_while_rendering(self) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._periodic_update_after_id = "after-periodic-update"
        app._closing = False
        app._restart_pending = False
        app._busy = False
        app._active_stage = WorkerStage.RENDERING
        app._listener_state = SimpleNamespace(
            active=True,
            stop_requested=False,
            job_running=True,
        )
        app._schedule_periodic_update_check = Mock()
        app._run_background = Mock()

        app._run_periodic_update_check()

        self.assertIsNone(app._periodic_update_after_id)
        app._run_background.assert_not_called()
        app._schedule_periodic_update_check.assert_called_once_with()

    @patch(
        "portable_pipe_tools.apps.render_worker_app."
        "resolve_render_worker_repository_root"
    )
    def test_periodic_update_check_runs_only_after_pausing_wait_countdown(
        self,
        resolve_repository_root: Mock,
    ) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._periodic_update_after_id = "after-periodic-update"
        app._closing = False
        app._restart_pending = False
        app._busy = False
        app._active_stage = WorkerStage.WAITING
        app._listener_state = SimpleNamespace(
            active=True,
            stop_requested=False,
            job_running=False,
        )
        app._cancel_listener_countdown = Mock()
        app._run_background = Mock(return_value=True)
        resolve_repository_root.return_value = "D:/DefectTools"

        app._run_periodic_update_check()

        app._cancel_listener_countdown.assert_called_once_with()
        app._run_background.assert_called_once()
        call = app._run_background.call_args
        self.assertEqual("Periodic Render Worker update check", call.kwargs["label"])
        self.assertEqual(app._periodic_update_succeeded, call.kwargs["on_success"])
        self.assertEqual(app._periodic_update_failed, call.kwargs["on_error"])

    def test_periodic_update_installs_and_restarts_only_while_active(self) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._listener_state = SimpleNamespace(active=True, stop_requested=False)
        app._restart_pending = False
        app._worker_git_branch = ""
        app._worker_git_commit = ""
        app._restart_after_id = None
        app.status_var = Mock()
        app._log = Mock()
        app._refresh_control_states = Mock()
        app.root = Mock()
        app.root.after.return_value = "after-restart"
        result = SimpleNamespace(
            update_installed=True,
            git_pull=SimpleNamespace(
                branch="main",
                commit_before="a" * 40,
                commit_after="b" * 40,
            ),
        )

        app._periodic_update_succeeded(result)

        self.assertTrue(app._restart_pending)
        self.assertEqual("after-restart", app._restart_after_id)
        app.root.after.assert_called_once_with(750, app._restart_after_update)

    def test_stop_request_wins_if_periodic_update_finishes_at_the_same_time(
        self,
    ) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._listener_state = SimpleNamespace(active=False, stop_requested=False)
        app._restart_pending = False
        app._worker_git_branch = ""
        app._worker_git_commit = ""
        app.status_var = Mock()
        app._log = Mock()
        app._refresh_control_states = Mock()
        app.root = Mock()
        result = SimpleNamespace(
            update_installed=True,
            git_pull=SimpleNamespace(
                branch="main",
                commit_before="a" * 40,
                commit_after="b" * 40,
            ),
        )

        app._periodic_update_succeeded(result)

        self.assertFalse(app._restart_pending)
        app.root.after.assert_not_called()
        app.status_var.set.assert_called_once_with(
            "Update installed — reopen worker to load it"
        )

    def test_periodic_update_failure_keeps_worker_listening(self) -> None:
        app = RenderWorkerApp.__new__(RenderWorkerApp)
        app._log = Mock()
        app._resume_listener_after_periodic_update = Mock()
        app._schedule_periodic_update_check = Mock()

        app._periodic_update_failed(ConnectionError("Git is unavailable"))

        app._resume_listener_after_periodic_update.assert_called_once_with()
        app._schedule_periodic_update_check.assert_called_once_with()
        self.assertIn("retry later", app._log.call_args.args[0])

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
