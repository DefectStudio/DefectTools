import errno
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.apps.render_worker_v2_app import RenderWorkerV2App
from portable_pipe_tools.render_farm.cloud_dispatch import CloudJobLease
from portable_pipe_tools.render_farm.cloud_queue import finish_cloud_claimed_job
from portable_pipe_tools.render_farm.listener import ContinuousWorkerState
from portable_pipe_tools.render_farm.project_workspace import (
    InsufficientDiskSpace, PreparationError, ProjectWorkspace, is_disk_space_error,
)
from portable_pipe_tools.render_farm.queue import QueuePaths
from portable_pipe_tools.render_farm.worker import WorkerResult


WORKSPACE = "portable_pipe_tools.render_farm.project_workspace"
CLOUD = "portable_pipe_tools.render_farm.cloud_queue"


class DiskSpaceErrorTests(unittest.TestCase):
    def test_native_wrapped_and_git_errors_are_recognized(self):
        windows_error = OSError("write failed")
        windows_error.winerror = 112
        wrapped = PreparationError("could not prepare")
        wrapped.__cause__ = OSError(errno.ENOSPC, "device write failed")
        for error in (
            InsufficientDiskSpace("need 3 GiB"), windows_error, wrapped,
            "cannot write: There is not enough space on the disk.",
            "disk quota exceeded",
        ):
            with self.subTest(error=error):
                self.assertTrue(is_disk_space_error(error))
        self.assertFalse(is_disk_space_error(PermissionError("access denied")))
        self.assertFalse(is_disk_space_error(PreparationError("cannot pull upstream")))

    def test_git_cannot_start_when_project_or_log_drive_is_exhausted(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workspace = ProjectWorkspace(directory / "logs", discovery_roots=())
            with patch(WORKSPACE + ".shutil.disk_usage", return_value=SimpleNamespace(free=0)), \
                 patch(WORKSPACE + ".subprocess.Popen") as launch:
                with self.assertRaises(InsufficientDiskSpace):
                    workspace.run(["fetch"], directory)
            launch.assert_not_called()
            self.assertFalse(workspace.root.exists())

    def test_git_disk_full_output_becomes_typed_resource_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workspace = ProjectWorkspace(directory / "logs", discovery_roots=())
            def launch(*args, stdout, **kwargs):
                stdout.write(b"cannot write data: There is not enough space on the disk.\n")
                return SimpleNamespace(poll=lambda: 1, returncode=1)
            with patch(WORKSPACE + ".subprocess.Popen", side_effect=launch):
                with self.assertRaises(InsufficientDiskSpace):
                    workspace.run(["lfs", "fetch"], directory)

    def test_running_download_is_terminated_when_disk_fills(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workspace = ProjectWorkspace(directory / "logs", discovery_roots=())
            process = Mock(pid=1234)
            process.poll.return_value = None
            with patch.object(workspace, "_check_emergency_disk_space", side_effect=[None, InsufficientDiskSpace("full")]), \
                 patch(WORKSPACE + ".subprocess.Popen", return_value=process), \
                 patch(WORKSPACE + ".time.monotonic", side_effect=[0, 1.1]), \
                 patch(WORKSPACE + ".subprocess.run") as terminate:
                with self.assertRaises(InsufficientDiskSpace):
                    workspace.run(["lfs", "fetch"], directory)
            if os.name == "nt":
                terminate.assert_called_once()
            process.wait.assert_called_once()

    def test_per_command_git_config_preserves_inherited_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            workspace = ProjectWorkspace(directory / "logs", discovery_roots=(),
                                         git_config={"filter.lfs.clean": "worker-clean"})
            process = SimpleNamespace(poll=lambda: 0, returncode=0)
            with patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "test.setting", "GIT_CONFIG_VALUE_0": "keep"}), \
                 patch(WORKSPACE + ".subprocess.Popen", return_value=process) as launch:
                workspace.run(["status"], directory)
            environment = launch.call_args.kwargs["env"]
            self.assertEqual("2", environment["GIT_CONFIG_COUNT"])
            self.assertEqual("keep", environment["GIT_CONFIG_VALUE_0"])
            self.assertEqual("filter.lfs.clean", environment["GIT_CONFIG_KEY_1"])
            self.assertEqual("worker-clean", environment["GIT_CONFIG_VALUE_1"])


class DiskFullCloudFinalizationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.job = {"job_id": "disk-job"}
        self.lease = CloudJobLease(job=self.job, lease_token="lease", lease_expires_at=0, stop_requested=False)
        self.dispatcher = Mock()

    def finish(self, *, success=False, reason="render failed", result_details=None):
        return finish_cloud_claimed_job(
            dispatcher=self.dispatcher, paths=QueuePaths.from_root(self.root),
            claimed_folder=self.root, job=self.job, worker_name="worker", lease=self.lease,
            success=success, reason=reason, result_details=result_details, shared_farm_root=self.root,
        )

    def test_disk_preflight_failure_reports_from_memory_without_writing_receipts(self):
        with patch(CLOUD + ".write_json_atomic") as write:
            with self.assertRaises(InsufficientDiskSpace):
                self.finish(reason="Insufficient disk space: need 3 GiB")
        write.assert_not_called()
        self.dispatcher.fail_job.assert_called_once()
        self.assertTrue(self.dispatcher.fail_job.call_args.kwargs["retryable"])

    def test_full_control_disk_does_not_prevent_reporting_a_terminal_result(self):
        full = OSError(errno.ENOSPC, "device is full")
        with patch(CLOUD + ".write_json_atomic", side_effect=full):
            with self.assertRaises(OSError) as raised:
                self.finish(success=True, reason="render completed")
        self.assertIs(full, raised.exception)
        self.dispatcher.complete_job.assert_called_once()

    def test_network_failure_cannot_replace_the_resource_error(self):
        self.dispatcher.fail_job.side_effect = RuntimeError("network unavailable")
        with self.assertLogs("render_worker.cloud_queue", level="ERROR"):
            with self.assertRaises(InsufficientDiskSpace):
                self.finish(reason="Insufficient disk space")

    def test_full_archive_drive_reports_render_result_then_stops(self):
        with patch(CLOUD + ".publish_cloud_render_logs", side_effect=OSError(errno.ENOSPC, "archive full")), \
             patch(CLOUD + ".write_json_atomic") as write:
            with self.assertRaises(OSError):
                self.finish(success=True, reason="render completed", result_details={"simulated": False})
        self.dispatcher.complete_job.assert_called_once()
        write.assert_not_called()


class DiskFullListenerTests(unittest.TestCase):
    def setUp(self):
        self.app = RenderWorkerV2App.__new__(RenderWorkerV2App)
        self.app._listener_state = ContinuousWorkerState()
        self.app._listener_state.start()
        self.app._listener_state.begin_job_check()
        self.app._worker_heartbeat = Mock()
        self.app._log = Mock()
        self.app._cancel_listener_countdown = Mock()
        self.app._finish_listener_stopped = Mock()
        self.app._schedule_listener_wait = Mock()
        self.app._schedule_listener_check_now = Mock()
        self.app._refresh_control_states = Mock()
        self.app.status_var = Mock()

    def test_disk_full_exception_stops_without_scheduling_another_claim(self):
        self.app._listener_job_check_errored(OSError(errno.ENOSPC, "device is full"))
        self.assertFalse(self.app._listener_state.active)
        self.app._finish_listener_stopped.assert_called_once()
        self.app._schedule_listener_wait.assert_not_called()
        self.app._schedule_listener_check_now.assert_not_called()

    def test_failed_resource_result_also_stops_after_successful_finalization(self):
        self.app._listener_job_check_finished(WorkerResult("requeued", Path("job"), "Insufficient disk space: assets"))
        self.assertFalse(self.app._listener_state.active)
        self.app._schedule_listener_check_now.assert_not_called()

    def test_other_job_errors_keep_normal_retry_behavior(self):
        self.app._listener_job_check_errored(RuntimeError("network unavailable"))
        self.assertTrue(self.app._listener_state.active)
        self.app._schedule_listener_wait.assert_called_once()

    def test_heartbeat_disk_full_cancels_the_active_sync_in_memory(self):
        self.app._worker_heartbeat.pop_errors.return_value = [OSError(errno.ENOSPC, "device is full")]
        self.app._poll_worker_heartbeat()
        self.assertTrue(self.app._listener_state.stop_requested)
        self.app._worker_heartbeat.request_stop.assert_called_once()
        self.app._schedule_listener_check_now.assert_not_called()


if __name__ == "__main__":
    unittest.main()
