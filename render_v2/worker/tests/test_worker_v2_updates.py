import errno
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.apps.render_worker_v2_app import (
    AUTOMATIC_START_DELAY_MS, PERIODIC_UPDATE_INTERVAL_MS, RenderWorkerV2App,
)
from portable_pipe_tools.apps import worker_v2_launcher as launcher
from portable_pipe_tools.render_farm.listener import ContinuousWorkerState
from portable_pipe_tools.render_farm.self_update import (
    BATCH_RESTART_ENVIRONMENT_VARIABLE, RENDER_WORKER_RESTART_EXIT_CODE,
    RESUME_AFTER_UPDATE_ENVIRONMENT_VARIABLE,
)
from portable_pipe_tools.render_farm.worker import WorkerStage


APP = "portable_pipe_tools.apps.render_worker_v2_app"


def update_result(changed=False):
    return SimpleNamespace(update_installed=changed, git_pull=SimpleNamespace(
        branch="main", commit_before="a" * 40,
        commit_after=("b" if changed else "a") * 40,
    ))


class WorkerV2UpdateTests(unittest.TestCase):
    def setUp(self):
        self.app = RenderWorkerV2App.__new__(RenderWorkerV2App)
        for name, value in {
            "_closing": False, "_busy": False, "_restart_pending": False,
            "_automatic_updates_enabled": True, "_auto_start_after_update": False,
            "_startup_update_complete": False, "_disk_space_stop_reason": None,
            "_automatic_start_after_id": None, "_periodic_update_after_id": None,
            "_restart_after_id": None, "_restart_requires_active_listener": False,
            "_active_stage": WorkerStage.WAITING, "_listener_configuration": object(),
        }.items():
            setattr(self.app, name, value)
        self.app._listener_state = ContinuousWorkerState()
        self.app._listener_state.start()
        self.app._worker_heartbeat = Mock()
        self.app.root = Mock()
        self.app.root.after.return_value = "timer"
        self.app.status_var = Mock()
        self.app._log = Mock()
        self.app._refresh_control_states = Mock()
        self.app._shutdown_application = Mock()
        self.app._cancel_listener_countdown = Mock()
        self.app._schedule_listener_check_now = Mock()
        self.app._finish_listener_stopped = Mock()

    def test_normal_open_checks_for_updates_without_starting_a_job(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.dict(os.environ, {"LOCALAPPDATA": temporary}), \
             patch.object(RenderWorkerV2App, "_begin_startup_update_check") as check:
            app = RenderWorkerV2App(settings_path=Path(temporary) / "worker.json")
            try:
                app.root.withdraw()
                self.assertFalse(app._startup_update_complete)
                self.assertFalse(app._listener_state.active)
                app.root.update()
                check.assert_called_once()
            finally:
                app._shutdown_application(0)

    def test_unchanged_initial_launch_enables_controls_without_autostart(self):
        self.app._startup_update_succeeded(update_result())
        self.assertTrue(self.app._startup_update_complete)
        self.app.root.after.assert_not_called()

    def test_update_restart_starts_worker_after_fresh_update_check(self):
        self.app._auto_start_after_update = True
        self.app._startup_update_succeeded(update_result())
        self.app.root.after.assert_called_once_with(AUTOMATIC_START_DELAY_MS, self.app._automatic_start_worker)
        self.app._start_worker = Mock()
        self.app._automatic_start_worker()
        self.app._start_worker.assert_called_once_with(require_confirmation=False)

    def test_new_startup_update_requests_reload_before_jobs(self):
        self.app._startup_update_succeeded(update_result(changed=True))
        self.assertTrue(self.app._restart_pending)
        self.assertFalse(self.app._startup_update_complete)
        self.app._restart_after_update()
        self.app._shutdown_application.assert_called_once_with(RENDER_WORKER_RESTART_EXIT_CODE)

    def test_active_worker_checks_every_two_minutes(self):
        self.assertEqual(120_000, PERIODIC_UPDATE_INTERVAL_MS)
        self.app._schedule_periodic_update_check()
        self.app.root.after.assert_called_once_with(120_000, self.app._run_periodic_update_check)

    def test_periodic_update_waits_until_render_has_finished(self):
        self.app._active_stage = WorkerStage.RENDERING
        self.app._listener_state.job_running = True
        self.app._run_background = Mock()
        self.app._run_periodic_update_check()
        self.app._run_background.assert_not_called()
        self.app.root.after.assert_called_once_with(120_000, self.app._run_periodic_update_check)

    def test_idle_check_pauses_claims_and_unchanged_result_resumes_listener(self):
        self.app._run_background = Mock(return_value=True)
        self.app._run_periodic_update_check()
        self.app._cancel_listener_countdown.assert_called_once()
        self.app._run_background.assert_called_once()
        self.app._periodic_update_succeeded(update_result())
        self.app._schedule_listener_check_now.assert_called_once()

    def test_new_idle_update_restarts_only_while_worker_is_active(self):
        self.app._periodic_update_succeeded(update_result(changed=True))
        self.assertTrue(self.app._restart_requires_active_listener)
        self.app._restart_after_update()
        self.app._shutdown_application.assert_called_once_with(RENDER_WORKER_RESTART_EXIT_CODE)

    def test_stop_while_update_is_in_progress_prevents_restart(self):
        self.app._listener_state.active = False
        self.app._periodic_update_succeeded(update_result(changed=True))
        self.app.root.after.assert_not_called()
        self.assertTrue(self.app._restart_pending)

    def test_stop_during_restart_countdown_prevents_restart(self):
        self.app._periodic_update_succeeded(update_result(changed=True))
        self.app._listener_state.active = False
        self.app._restart_after_update()
        self.app._shutdown_application.assert_not_called()

    def test_disk_full_during_update_stops_and_cancels_future_work(self):
        self.app._periodic_update_after_id = "update-timer"
        self.app._automatic_start_after_id = "auto-timer"
        self.app._periodic_update_failed(OSError(errno.ENOSPC, "disk full"))
        self.assertFalse(self.app._listener_state.active)
        self.assertIsNone(self.app._periodic_update_after_id)
        self.assertIsNone(self.app._automatic_start_after_id)
        self.app._schedule_listener_check_now.assert_not_called()

    def test_network_update_failure_resumes_claims_and_retries_later(self):
        self.app._periodic_update_failed(ConnectionError("offline"))
        self.assertTrue(self.app._listener_state.active)
        self.app._schedule_listener_check_now.assert_called_once()
        self.app.root.after.assert_called_once_with(120_000, self.app._run_periodic_update_check)

    def test_resource_stop_cannot_be_bypassed_by_automatic_restart_or_start(self):
        self.app._disk_space_stop_reason = "Free disk space"
        self.app._start_worker = Mock()
        self.app._restart_after_update()
        self.app._automatic_start_worker()
        self.app._schedule_periodic_update_check()
        self.app._shutdown_application.assert_not_called()
        self.app._start_worker.assert_not_called()
        self.app.root.after.assert_not_called()


class WorkerV2RestartLauncherTests(unittest.TestCase):
    def test_direct_python_restart_uses_fresh_interpreter_and_resumes_after_check(self):
        first = Mock()
        first.run.return_value = RENDER_WORKER_RESTART_EXIT_CODE
        second = Mock()
        second.run.return_value = 0
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(launcher, "RenderWorkerV2App", side_effect=[first, second]) as apps, \
             patch.object(launcher.subprocess, "Popen") as spawn:
            self.assertEqual(0, launcher.run_gui())
            self.assertEqual([launcher.sys.executable, "-m", "portable_pipe_tools.apps.worker_v2_launcher"], spawn.call_args.args[0])
            restart_environment = spawn.call_args.kwargs["env"]
            self.assertEqual("1", restart_environment[RESUME_AFTER_UPDATE_ENVIRONMENT_VARIABLE])
            self.assertEqual(os.getcwd(), spawn.call_args.kwargs["cwd"])
            with patch.dict(os.environ, restart_environment, clear=True):
                self.assertEqual(0, launcher.run_gui())
        self.assertEqual([False, True], [call.kwargs["auto_start"] for call in apps.call_args_list])

    def test_batch_supervisor_receives_restart_code_without_duplicate_process(self):
        app = Mock()
        app.run.return_value = RENDER_WORKER_RESTART_EXIT_CODE
        with patch.dict(os.environ, {BATCH_RESTART_ENVIRONMENT_VARIABLE: "1"}, clear=True), \
             patch.object(launcher, "RenderWorkerV2App", return_value=app), \
             patch.object(launcher.subprocess, "Popen") as spawn:
            self.assertEqual(RENDER_WORKER_RESTART_EXIT_CODE, launcher.run_gui())
        spawn.assert_not_called()

    def test_canonical_source_batch_relaunches_with_explicit_resume_context(self):
        batch = Path(__file__).resolve().parents[3] / "tools" / "render_worker_v2.bat"
        source = batch.read_text()
        self.assertIn('set "DEFECT_WORKER_V2_BATCH_RESTART=1"', source)
        self.assertIn('if "%WORKER_EXIT_CODE%"=="75"', source)
        self.assertIn('set "DEFECT_WORKER_V2_RESUME_AFTER_UPDATE=1"', source)
        self.assertIn("goto launch", source)
        self.assertIn("-m portable_pipe_tools.apps.worker_v2_launcher", source)


if __name__ == "__main__":
    unittest.main()
