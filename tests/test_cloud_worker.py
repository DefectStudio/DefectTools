from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from portable_pipe_tools.render_farm.cloud_dispatch import (
    CloudClaimResult,
    CloudJobLease,
    DispatcherConnectionError,
)
from portable_pipe_tools.render_farm.cloud_queue import (
    PENDING_DISPATCHER_UPDATE_FILENAME,
    reconcile_pending_cloud_updates,
)
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
        self.fail_completion_once = False
        self.stop_requested = False
        self.stop_acknowledged: list[str] = []

    def claim_job(self, worker_id: str, **_kwargs) -> CloudClaimResult:
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
        self.failed.append((job_id, worker_id, retryable))
        return {"ok": True}


class CloudWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.farm_root = Path(self.temporary_directory.name) / "RenderFarm"
        self.paths = create_queue_folders(self.farm_root)

    def _lease_for_queued_job(self, worker: str = "CLOUD-WORKER") -> CloudJobLease:
        queued_folder = create_test_job(self.farm_root)
        job = read_json_object(queued_folder / JOB_FILENAME)
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
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertEqual([(lease.job_id, "CLOUD-WORKER")], dispatcher.completed)
        self.assertFalse(
            (result.final_folder / PENDING_DISPATCHER_UPDATE_FILENAME).exists()
        )

    def test_missing_dropbox_package_releases_cloud_lease(self) -> None:
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
        )

        self.assertIsNone(result)
        self.assertEqual(1, len(dispatcher.released))
        self.assertEqual("NOT_SYNCED_YET", dispatcher.released[0][0])

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
            )

        completed_folders = list(self.paths.render_complete.iterdir())
        self.assertEqual(1, len(completed_folders))
        pending_path = completed_folders[0] / PENDING_DISPATCHER_UPDATE_FILENAME
        self.assertTrue(pending_path.is_file())

        reconciled = reconcile_pending_cloud_updates(
            self.paths,
            dispatcher,
            minimum_age_seconds=0,
        )

        self.assertEqual(completed_folders, reconciled)
        self.assertFalse(pending_path.exists())
        self.assertEqual([(lease.job_id, "CLOUD-WORKER")], dispatcher.completed)

    def test_real_render_renews_cloud_lease(self) -> None:
        lease = self._lease_for_queued_job()
        dispatcher = FakeDispatcher(lease)

        def fake_unreal_runner(**kwargs) -> UnrealExecutionResult:
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
        )

        self.assertIsNotNone(result)
        self.assertEqual(1, dispatcher.heartbeat_count)


if __name__ == "__main__":
    unittest.main()
