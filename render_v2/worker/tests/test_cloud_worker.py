from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.cloud_dispatch import (
    CloudClaimResult,
    CloudJobLease,
    DispatcherConnectionError,
    DispatcherError,
)
from portable_pipe_tools.render_farm.cloud_queue import (
    INTERRUPTED_JOB_FILENAME,
    PENDING_DISPATCHER_UPDATE_FILENAME,
    STALE_DISPATCHER_UPDATE_PREFIX,
    reconcile_pending_cloud_updates,
)
from portable_pipe_tools.render_farm.git_sync import GitPullError
from portable_pipe_tools.render_farm.queue import (
    DISPATCHER_COORDINATION_FIELD,
    JOB_FILENAME,
    create_queue_folders,
    read_json_object,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.test_job import create_test_job
from portable_pipe_tools.render_farm.unreal_runner import UnrealExecutionResult
from portable_pipe_tools.render_farm.worker import run_once


class FakeDispatcher:
    def __init__(self, lease: CloudJobLease | None) -> None:
        self.lease = lease
        self.released: list[tuple[str, str, str]] = []
        self.completed: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str, bool]] = []
        self.heartbeat_count = 0
        self.heartbeat_payloads: list[dict] = []
        self.heartbeat_error = False
        self.fail_completion_once = False
        self.stale_failure_job_ids: set[str] = set()
        self.stop_requested = False
        self.stop_acknowledged: list[str] = []
        self.claim_count = 0
        self.last_claim_kwargs: dict = {}

    def claim_job(self, worker_id: str, **kwargs) -> CloudClaimResult:
        self.claim_count += 1
        self.last_claim_kwargs = dict(kwargs)
        lease = self.lease
        self.lease = None
        return CloudClaimResult(
            lease=lease,
            stop_requested=self.stop_requested,
        )

    def acknowledge_worker_stop(self, worker_id: str) -> dict:
        self.stop_acknowledged.append(worker_id)
        return {"ok": True}

    def release_job(
        self,
        job_id: str,
        worker_id: str,
        _lease_token: str,
        *,
        reason: str,
    ) -> dict:
        self.released.append((job_id, worker_id, reason))
        return {"ok": True}

    def heartbeat_job(self, *_args, **_kwargs) -> dict:
        self.heartbeat_count += 1
        self.heartbeat_payloads.append(dict(_kwargs))
        if self.heartbeat_error:
            raise DispatcherConnectionError("intentional heartbeat outage")
        return {"ok": True, "stop_requested": False}

    def complete_job(
        self,
        job_id: str,
        worker_id: str,
        _lease_token: str,
        **_kwargs,
    ) -> dict:
        if self.fail_completion_once:
            self.fail_completion_once = False
            raise DispatcherConnectionError("intentional outage")
        self.completed.append((job_id, worker_id))
        return {"ok": True}

    def fail_job(
        self,
        job_id: str,
        worker_id: str,
        _lease_token: str,
        *,
        retryable: bool,
        **_kwargs,
    ) -> dict:
        if job_id in self.stale_failure_job_ids:
            raise DispatcherError(
                "The job is no longer owned by this worker lease.",
                status=409,
                code="lease_lost",
            )
        self.failed.append((job_id, worker_id, retryable))
        return {"ok": True}


class CloudWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.farm_root = Path(self.temporary_directory.name) / "RenderFarm"
        self.paths = create_queue_folders(self.farm_root)
        self.cloud_spool_root = (
            Path(self.temporary_directory.name) / "CloudJobSpool"
        )
        self.cloud_paths = create_queue_folders(self.cloud_spool_root)

    def _lease_for_queued_job(self, worker: str = "CLOUD-WORKER") -> CloudJobLease:
        queued_folder = create_test_job(self.farm_root)
        job = read_json_object(queued_folder / JOB_FILENAME)
        job[DISPATCHER_COORDINATION_FIELD] = "cloud"
        write_json_atomic(queued_folder / JOB_FILENAME, job)
        job["status"] = "rendering"
        job["worker"] = worker
        job["attempt"] = 1
        return CloudJobLease(
            job=job,
            lease_token=f"lease-{job['job_id']}",
            lease_expires_at=int(time.time()) + 300,
            stop_requested=False,
        )

    def test_cloud_claim_completes_exact_package_and_dispatcher(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=True,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            dispatcher_capabilities={
                "git_branch": "main",
                "git_commit": "abc123",
            },
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertEqual([(lease.job_id, "CLOUD-WORKER")], dispatcher.completed)
        self.assertEqual(
            "abc123",
            dispatcher.last_claim_kwargs["capabilities"]["git_commit"],
        )
        self.assertFalse(
            (result.final_folder / PENDING_DISPATCHER_UPDATE_FILENAME).exists()
        )

    def test_cloud_payload_materializes_without_a_dropbox_package(self) -> None:
        lease = CloudJobLease(
            job={
                "job_id": "NOT_SYNCED_YET",
                "status": "rendering",
                "worker": "CLOUD-WORKER",
                "attempt": 1,
                "priority": 50,
                "submitted_utc": "2026-08-16T00:00:00Z",
            },
            lease_token="not-synced-lease",
            lease_expires_at=int(time.time()) + 300,
            stop_requested=False,
        )
        dispatcher = FakeDispatcher(lease)

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=True,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertEqual([], dispatcher.released)
        self.assertEqual(
            [("NOT_SYNCED_YET", "CLOUD-WORKER")],
            dispatcher.completed,
        )

    def test_cloud_render_logs_publish_to_dropbox_terminal_folders(self) -> None:
        for success, state_folder_name in (
            (True, "03_RenderComplete"),
            (False, "04_RenderFailed"),
        ):
            with self.subTest(success=success):
                job_id = f"LOG_ARCHIVE_{'SUCCESS' if success else 'FAILURE'}"
                lease = CloudJobLease(
                    job={
                        "job_id": job_id,
                        "status": "rendering",
                        "worker": "CLOUD-WORKER",
                        "attempt": 2,
                        "priority": 50,
                        "submitted_utc": "2026-08-20T00:00:00Z",
                    },
                    lease_token=f"lease-{job_id}",
                    lease_expires_at=int(time.time()) + 300,
                    stop_requested=False,
                )
                dispatcher = FakeDispatcher(lease)

                def fake_unreal_runner(**kwargs) -> UnrealExecutionResult:
                    claimed_folder = Path(kwargs["claimed_folder"])
                    (claimed_folder / "unreal.log").write_text(
                        "full Unreal log",
                        encoding="utf-8",
                    )
                    (claimed_folder / "unreal_stdout.log").write_text(
                        "full Unreal stdout",
                        encoding="utf-8",
                    )
                    (claimed_folder / "git_pull.log").write_text(
                        "Git transcript",
                        encoding="utf-8",
                    )
                    return UnrealExecutionResult(
                        success=success,
                        reason="Intentional archive test",
                        exit_code=0 if success else 1,
                    )

                result = run_once(
                    self.farm_root,
                    "CLOUD-WORKER",
                    simulate_success=False,
                    render_with_unreal=True,
                    unreal_runner=fake_unreal_runner,
                    minimum_stage_seconds=0,
                    dispatcher_client=dispatcher,
                    cloud_spool_root=self.cloud_spool_root,
                )

                self.assertIsNotNone(result)
                archive_folder = (
                    self.farm_root
                    / state_folder_name
                    / f"{job_id}__CLOUD-WORKER__attempt_002"
                )
                self.assertEqual(
                    {"unreal.log", "unreal_stdout.log", "git_pull.log"},
                    {path.name for path in archive_folder.iterdir()},
                )
                self.assertFalse((archive_folder / JOB_FILENAME).exists())

    def test_dropbox_log_publication_failure_does_not_fail_cloud_job(self) -> None:
        blocked_root = Path(self.temporary_directory.name) / "blocked-render-farm"
        blocked_root.write_text(
            "This path intentionally blocks mkdir.",
            encoding="utf-8",
        )
        lease = CloudJobLease(
            job={
                "job_id": "LOG_ARCHIVE_BLOCKED",
                "status": "rendering",
                "worker": "CLOUD-WORKER",
                "attempt": 1,
                "priority": 50,
                "submitted_utc": "2026-08-20T00:00:00Z",
            },
            lease_token="lease-log-archive-blocked",
            lease_expires_at=int(time.time()) + 300,
            stop_requested=False,
        )
        dispatcher = FakeDispatcher(lease)

        def fake_unreal_runner(**kwargs) -> UnrealExecutionResult:
            claimed_folder = Path(kwargs["claimed_folder"])
            (claimed_folder / "unreal.log").write_text(
                "This local log must survive Dropbox failure.",
                encoding="utf-8",
            )
            return UnrealExecutionResult(
                success=True,
                reason="Dropbox publication failure is non-fatal",
                exit_code=0,
            )

        result = run_once(
            blocked_root,
            "CLOUD-WORKER",
            simulate_success=False,
            render_with_unreal=True,
            unreal_runner=fake_unreal_runner,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertEqual(
            [(lease.job_id, "CLOUD-WORKER")],
            dispatcher.completed,
        )

    def test_cloud_git_preflight_failure_releases_d1_lease(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)

        def fail_git_sync(_project_directory: Path):
            raise GitPullError("intentional Git failure")

        local_uproject = Path(self.temporary_directory.name) / "S3Bishop.uproject"
        local_uproject.touch()
        with self.assertRaisesRegex(GitPullError, "intentional Git failure"):
            run_once(
                self.farm_root,
                "CLOUD-WORKER",
                simulate_success=True,
                render_with_unreal=True,
                unreal_runner=lambda *_args, **_kwargs: None,
                local_uproject=local_uproject,
                git_sync=fail_git_sync,
                minimum_stage_seconds=0,
                dispatcher_client=dispatcher,
                cloud_spool_root=self.cloud_spool_root,
            )

        self.assertEqual(1, len(dispatcher.released))
        self.assertEqual(lease.job_id, dispatcher.released[0][0])
        self.assertIn("Git preflight failed", dispatcher.released[0][2])
        self.assertTrue(
            (self.cloud_paths.needs_rendering / lease.job_id).is_dir()
        )

    def test_interrupted_local_staging_folder_is_recovered(self) -> None:
        lease = self._lease_for_queued_job()
        staging_folder = self.cloud_paths.submitting / lease.job_id
        staging_folder.mkdir()
        write_json_atomic(staging_folder / JOB_FILENAME, {"incomplete": True})
        dispatcher = FakeDispatcher(lease)

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=True,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertFalse(staging_folder.exists())
        self.assertEqual([(lease.job_id, "CLOUD-WORKER")], dispatcher.completed)

    def test_cloud_claim_recovers_package_stranded_by_expired_worker(self) -> None:
        lease = self._lease_for_queued_job(worker="RECOVERY-WORKER")
        queued_folder = self.cloud_paths.needs_rendering / lease.job_id
        queued_folder.mkdir()
        stranded_job = dict(lease.job)
        stranded_job.update(
            {
                "status": "rendering",
                "worker": "CRASHED-WORKER",
                "attempt": 1,
            }
        )
        write_json_atomic(queued_folder / JOB_FILENAME, stranded_job)
        stranded_folder = (
            self.cloud_paths.is_rendering / f"{lease.job_id}__CRASHED-WORKER"
        )
        queued_folder.rename(stranded_folder)
        dispatcher = FakeDispatcher(lease)

        result = run_once(
            self.farm_root,
            "RECOVERY-WORKER",
            simulate_success=True,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertFalse(stranded_folder.exists())
        self.assertEqual([(lease.job_id, "RECOVERY-WORKER")], dispatcher.completed)

    def test_filesystem_worker_skips_cloud_coordinated_package(self) -> None:
        queued_folder = create_test_job(self.farm_root)
        job_path = queued_folder / JOB_FILENAME
        job = read_json_object(job_path)
        job[DISPATCHER_COORDINATION_FIELD] = "cloud"
        write_json_atomic(job_path, job)

        result = run_once(
            self.farm_root,
            "FILESYSTEM-WORKER",
            simulate_success=True,
            minimum_stage_seconds=0,
        )

        self.assertIsNone(result)
        self.assertTrue(queued_folder.is_dir())

    def test_cloud_stop_request_is_acknowledged(self) -> None:
        dispatcher = FakeDispatcher(None)
        dispatcher.stop_requested = True

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=True,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("stopped", result.status)
        self.assertEqual(["CLOUD-WORKER"], dispatcher.stop_acknowledged)

    def test_failed_render_requeues_and_updates_dispatcher(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=False,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("requeued", result.status)
        self.assertEqual([(lease.job_id, "CLOUD-WORKER", True)], dispatcher.failed)
        queued_job = read_json_object(result.final_folder / JOB_FILENAME)
        self.assertEqual(["CLOUD-WORKER"], queued_job["blacklisted_workers"])

    def test_network_outage_leaves_recoverable_completion_receipt(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        dispatcher.fail_completion_once = True

        with self.assertRaises(DispatcherConnectionError):
            run_once(
                self.farm_root,
                "CLOUD-WORKER",
                simulate_success=True,
                minimum_stage_seconds=0,
                dispatcher_client=dispatcher,
                cloud_spool_root=self.cloud_spool_root,
            )

        completed_folders = list(self.cloud_paths.render_complete.iterdir())
        self.assertEqual(1, len(completed_folders))
        pending_path = completed_folders[0] / PENDING_DISPATCHER_UPDATE_FILENAME
        self.assertTrue(pending_path.is_file())

        reconciled = reconcile_pending_cloud_updates(
            self.cloud_paths,
            dispatcher,
            minimum_age_seconds=0,
        )

        self.assertEqual(completed_folders, reconciled)
        self.assertFalse(pending_path.exists())
        self.assertEqual([(lease.job_id, "CLOUD-WORKER")], dispatcher.completed)

    def test_stale_terminal_receipt_is_quarantined_without_blocking_claim(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        stale_job_id = "STALE-RELEASED-JOB"
        dispatcher.stale_failure_job_ids.add(stale_job_id)
        stale_folder = (
            self.cloud_paths.render_complete / "STALE-RELEASED-JOB__OLD-WORKER"
        )
        stale_folder.mkdir()
        pending_path = stale_folder / PENDING_DISPATCHER_UPDATE_FILENAME
        write_json_atomic(
            pending_path,
            {
                "schema_version": 1,
                "created_utc": "2026-08-20T09:05:00.000Z",
                "action": "fail",
                "job_id": stale_job_id,
                "worker_id": "OLD-WORKER",
                "lease_token": "released-lease-token",
                "reason": "Dropbox finalization failed after the lease was released",
                "retryable": True,
                "result": {},
                "invalid_package": False,
            },
        )

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=True,
            minimum_stage_seconds=0,
            dispatcher_client=dispatcher,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertEqual(1, dispatcher.claim_count)
        self.assertFalse(pending_path.exists())
        quarantined = list(
            stale_folder.glob(f"{STALE_DISPATCHER_UPDATE_PREFIX}_*.json")
        )
        self.assertEqual(1, len(quarantined))
        self.assertEqual(
            stale_job_id,
            read_json_object(quarantined[0])["job_id"],
        )

    def test_real_render_renews_cloud_lease(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)

        def fake_unreal_runner(**kwargs) -> UnrealExecutionResult:
            self.assertEqual(self.farm_root, kwargs["render_farm_root"])
            self.assertNotEqual(
                self.farm_root,
                Path(kwargs["claimed_folder"]).parent.parent,
            )
            time.sleep(0.02)
            self.assertFalse(kwargs["should_cancel"]())
            return UnrealExecutionResult(
                success=True,
                reason="Fake Unreal render completed",
                exit_code=0,
            )

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=False,
            minimum_stage_seconds=0,
            render_with_unreal=True,
            unreal_runner=fake_unreal_runner,
            dispatcher_client=dispatcher,
            dispatcher_heartbeat_interval_seconds=0.01,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        self.assertEqual(3, dispatcher.heartbeat_count)

    def test_render_progress_is_batched_into_one_minute_heartbeats(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        now = [0.0]

        def render(**kwargs):
            self.assertIsNone(kwargs["timeout_seconds"])
            for seconds, frame in ((30, 10), (60, 20), (90, 30), (120, 40)):
                now[0] = float(seconds)
                kwargs["progress_callback"](dict(schema_version=1, phase="rendering",
                                                  progress=float(frame), current_frame=frame,
                                                  total_frames=100, last_progress_age_seconds=0,
                                                  elapsed_seconds=seconds))
                self.assertFalse(kwargs["should_cancel"]())
            return UnrealExecutionResult(True, "Rendered", 0)

        result = run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                          render_with_unreal=True, unreal_runner=render, dispatcher_client=dispatcher,
                          cloud_spool_root=self.cloud_spool_root, render_timeout_seconds=None,
                          monotonic=lambda: now[0])
        self.assertEqual("complete", result.status)
        self.assertEqual(4, dispatcher.heartbeat_count)
        self.assertEqual([20.0, 40.0, 40.0], [p["progress"] for p in dispatcher.heartbeat_payloads
                                               if "progress" in p])
        self.assertEqual(40, dispatcher.heartbeat_payloads[-1]["progress_details"]["current_frame"])

    def test_unstoppable_unreal_blocks_job_instead_of_reassigning_it(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        result = run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                          render_with_unreal=True, dispatcher_client=dispatcher,
                          cloud_spool_root=self.cloud_spool_root,
                          unreal_runner=lambda **_: UnrealExecutionResult(
                              False, "Could not stop Unreal; restart node", None,
                              process_still_running=True))
        self.assertEqual("blocked", result.status)
        self.assertEqual([(lease.job_id, "CLOUD-WORKER", False)], dispatcher.failed)
        self.assertEqual([], dispatcher.completed)

    def test_blocked_worker_stays_blocked_if_receipt_and_network_reporting_fail(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        def offline(*args, **kwargs):
            raise DispatcherConnectionError("offline during quarantine")
        dispatcher.fail_job = offline
        module = "portable_pipe_tools.render_farm.worker"
        with patch(module + ".finish_cloud_claimed_job") as finalize, \
             patch(module + ".write_json_atomic", side_effect=OSError("control disk unavailable")):
            result = run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                              render_with_unreal=True, dispatcher_client=dispatcher,
                              cloud_spool_root=self.cloud_spool_root,
                              unreal_runner=lambda **_: UnrealExecutionResult(
                                  False, "Unreal is still running", None, process_still_running=True))
        self.assertEqual("blocked", result.status)
        finalize.assert_not_called()
        self.assertEqual([], dispatcher.completed)

    def test_heartbeat_outage_cancels_before_cloud_lease_can_expire(self) -> None:
        initial_lease = self._lease_for_queued_job()
        lease = CloudJobLease(
            job=initial_lease.job,
            lease_token=initial_lease.lease_token,
            lease_expires_at=int(time.time()) + 1,
            stop_requested=False,
        )
        dispatcher = FakeDispatcher(lease)
        dispatcher.heartbeat_error = True

        def fake_unreal_runner(**kwargs) -> UnrealExecutionResult:
            time.sleep(0.02)
            self.assertTrue(kwargs["should_cancel"]())
            return UnrealExecutionResult(
                success=False,
                reason="Canceled by lease safety test",
                exit_code=-1,
            )

        result = run_once(
            self.farm_root,
            "CLOUD-WORKER",
            simulate_success=False,
            minimum_stage_seconds=0,
            render_with_unreal=True,
            unreal_runner=fake_unreal_runner,
            dispatcher_client=dispatcher,
            dispatcher_heartbeat_interval_seconds=0.01,
            cloud_spool_root=self.cloud_spool_root,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("requeued", result.status)
        self.assertEqual(1, dispatcher.heartbeat_count)
        self.assertEqual([(lease.job_id, "CLOUD-WORKER", True)], dispatcher.failed)

    def test_job_stop_before_preparation_skips_unreal_and_keeps_listener_eligible(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        def revoked(*_args, **_kwargs):
            raise DispatcherError("Manager stopped this job", status=409, code="job_control_requested")
        dispatcher.heartbeat_job = revoked
        with patch("portable_pipe_tools.render_farm.worker.execute_unreal_job") as runner:
            result = run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                              render_with_unreal=True, unreal_runner=runner, dispatcher_client=dispatcher,
                              cloud_spool_root=self.cloud_spool_root)
        runner.assert_not_called()
        self.assertEqual("job_stopped", result.status)
        self.assertTrue((result.final_folder / INTERRUPTED_JOB_FILENAME).is_file())
        self.assertFalse((result.final_folder / PENDING_DISPATCHER_UPDATE_FILENAME).exists())
        self.assertEqual([], dispatcher.failed)
        self.assertEqual([], dispatcher.completed)
        self.assertEqual([(lease.job_id, "CLOUD-WORKER", "Interrupted job process cleanup completed")],
                         dispatcher.released)
        self.assertEqual([], dispatcher.stop_acknowledged)

    def test_requeue_cancels_active_preparation_and_cancel_stays_set(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        now = [0.0]
        record_release = dispatcher.release_job
        def acknowledge_revoked_lease(*args, **kwargs):
            record_release(*args, **kwargs)
            raise DispatcherError("Cleanup acknowledged for revoked lease", status=409, code="lease_lost")
        dispatcher.release_job = acknowledge_revoked_lease
        def render(**kwargs):
            (Path(kwargs["claimed_folder"]) / "unreal.log").write_text("attempt log", encoding="utf-8")
            def revoked(*_args, **_kwargs):
                raise DispatcherError("Manager requeued this job", status=409, code="lease_lost",
                                      response={"error": {"details": {"action": "requeue",
                                                                       "job_control_requested": True}}})
            dispatcher.heartbeat_job = revoked
            now[0] = 5.0
            self.assertTrue(kwargs["should_cancel"]())
            now[0] = 5.1
            self.assertTrue(kwargs["should_cancel"]())
            return UnrealExecutionResult(False, "Preparation canceled", None, cancelled=True)
        result = run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                          render_with_unreal=True, unreal_runner=render, dispatcher_client=dispatcher,
                          cloud_spool_root=self.cloud_spool_root, monotonic=lambda: now[0],
                          dispatcher_heartbeat_interval_seconds=5)
        self.assertEqual("job_stopped", result.status)
        self.assertIn("Manager requested requeue", result.reason)
        self.assertEqual("attempt log", (result.final_folder / "unreal.log").read_text(encoding="utf-8"))
        self.assertEqual([], dispatcher.failed)
        self.assertEqual([], dispatcher.completed)
        self.assertEqual([(lease.job_id, "CLOUD-WORKER", "Interrupted job process cleanup completed")],
                         dispatcher.released)
        # A job-only cancellation does not consume the worker STOP command and
        # does not leave a stale local outbox that blocks the next queue check.
        self.assertEqual([], dispatcher.stop_acknowledged)
        self.assertEqual([], reconcile_pending_cloud_updates(self.cloud_paths, dispatcher, minimum_age_seconds=0))
        self.assertIsNone(run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                                   dispatcher_client=dispatcher, cloud_spool_root=self.cloud_spool_root))

    def test_stop_racing_with_successful_finalization_quarantines_receipt(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        def interrupted(*_args, **_kwargs):
            raise DispatcherError("Manager stopped this job", status=409, code="job_control_requested")
        dispatcher.complete_job = interrupted
        result = run_once(self.farm_root, "CLOUD-WORKER", True, minimum_stage_seconds=0,
                          dispatcher_client=dispatcher, cloud_spool_root=self.cloud_spool_root)
        self.assertEqual("job_stopped", result.status)
        self.assertTrue((result.final_folder / INTERRUPTED_JOB_FILENAME).exists())
        self.assertFalse((result.final_folder / PENDING_DISPATCHER_UPDATE_FILENAME).exists())
        self.assertEqual(1, len(list(result.final_folder.glob(f"{STALE_DISPATCHER_UPDATE_PREFIX}_*.json"))))
        self.assertEqual([], dispatcher.failed)

    def test_interrupted_job_with_live_unreal_still_blocks_worker(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        now = [0.0]
        def render(**kwargs):
            def interrupted(*_args, **_kwargs):
                raise DispatcherError("Manager stopped this job", status=409, code="job_control_requested")
            dispatcher.heartbeat_job = interrupted
            dispatcher.fail_job = interrupted
            now[0] = 5.0
            self.assertTrue(kwargs["should_cancel"]())
            return UnrealExecutionResult(False, "Unreal is still running", None, process_still_running=True)
        result = run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                          render_with_unreal=True, unreal_runner=render, dispatcher_client=dispatcher,
                          cloud_spool_root=self.cloud_spool_root, monotonic=lambda: now[0],
                          dispatcher_heartbeat_interval_seconds=5)
        self.assertEqual("blocked", result.status)
        self.assertTrue((result.final_folder / "worker_blocked.json").is_file())
        self.assertEqual([], dispatcher.released)

    def test_cleanup_ack_outage_keeps_worker_available_for_a_different_job(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)
        def interrupted(*_args, **_kwargs):
            raise DispatcherError("Manager requeued this job", status=409, code="lease_lost")
        def offline(*_args, **_kwargs):
            raise DispatcherConnectionError("offline during cleanup acknowledgement")
        dispatcher.heartbeat_job = interrupted
        dispatcher.release_job = offline
        with self.assertLogs("render_worker", level="WARNING") as logs:
            result = run_once(self.farm_root, "CLOUD-WORKER", False, minimum_stage_seconds=0,
                              render_with_unreal=True, unreal_runner=lambda **_: self.fail("Unreal started"),
                              dispatcher_client=dispatcher, cloud_spool_root=self.cloud_spool_root)
        self.assertEqual("job_stopped", result.status)
        self.assertTrue((result.final_folder / INTERRUPTED_JOB_FILENAME).is_file())
        self.assertTrue(any("old lease expires" in line for line in logs.output))
        # The interrupted job stays behind D1's cleanup barrier. This worker
        # remains eligible for other jobs even when the acknowledgement is offline.
        next_job = dict(lease.job, job_id=f"{lease.job_id}_next")
        dispatcher.lease = CloudJobLease(next_job, "next-lease", int(time.time()) + 300, False)
        next_result = run_once(self.farm_root, "CLOUD-WORKER", True, minimum_stage_seconds=0,
                               dispatcher_client=dispatcher, cloud_spool_root=self.cloud_spool_root)
        self.assertEqual("complete", next_result.status)
        self.assertEqual([(next_job["job_id"], "CLOUD-WORKER")], dispatcher.completed)
        self.assertEqual([], dispatcher.stop_acknowledged)


if __name__ == "__main__":
    unittest.main()
