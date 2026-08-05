from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.git_sync import (
    GIT_PULL_LOG_FILENAME,
    GitPullError,
    GitPullResult,
)
from portable_pipe_tools.render_farm.queue import (
    JOB_FILENAME,
    RESULT_FILENAME,
    claim_next_job,
    create_queue_folders,
    list_job_candidates,
    read_json_object,
    rename_path_with_retry,
    retry_transient_windows_lock,
    write_json_atomic,
)
from portable_pipe_tools.render_farm.test_job import create_test_job
from portable_pipe_tools.render_farm.unreal_runner import UnrealExecutionResult
from portable_pipe_tools.render_farm.worker import WorkerStage, run_once


class RenderFarmPrototypeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.farm_root = Path(self.temporary_directory.name) / "RenderFarm"
        self.paths = create_queue_folders(self.farm_root)

    def test_create_test_job_publishes_complete_folder(self) -> None:
        queued_folder = create_test_job(self.farm_root)

        self.assertEqual([], list(self.paths.submitting.iterdir()))
        self.assertTrue(queued_folder.is_dir())
        job = read_json_object(queued_folder / JOB_FILENAME)
        self.assertEqual("queued", job["status"])
        self.assertEqual(1001, job["frame_start"])
        self.assertEqual(1100, job["frame_end"])
        self.assertEqual([], job["blacklisted_workers"])

    def test_claim_prefers_higher_priority_then_older_submission(self) -> None:
        self._queue_job("low", priority=10, submitted_utc="2026-08-03T01:00:00.000Z")
        self._queue_job("high-new", priority=90, submitted_utc="2026-08-03T03:00:00.000Z")
        self._queue_job("high-old", priority=90, submitted_utc="2026-08-03T02:00:00.000Z")

        claimed = claim_next_job(self.paths, "RENDER-03")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual("high-old__RENDER-03", claimed.name)
        self.assertFalse((self.paths.needs_rendering / "high-old").exists())

    def test_second_worker_cannot_claim_already_claimed_job(self) -> None:
        create_test_job(self.farm_root)

        first_claim = claim_next_job(self.paths, "RENDER-02")
        second_claim = claim_next_job(self.paths, "RENDER-03")

        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)

    def test_claim_skips_jobs_that_blacklist_the_worker(self) -> None:
        self._queue_job("high", priority=90, submitted_utc="2026-08-03T01:00:00.000Z")
        self._queue_job("low", priority=10, submitted_utc="2026-08-03T02:00:00.000Z")
        high_job_path = self.paths.needs_rendering / "high" / JOB_FILENAME
        high_job = read_json_object(high_job_path)
        high_job["blacklisted_workers"] = ["render-03"]
        write_json_atomic(high_job_path, high_job)

        claimed = claim_next_job(self.paths, "RENDER-03")

        self.assertIsNotNone(claimed)
        assert claimed is not None
        self.assertEqual("low__RENDER-03", claimed.name)
        self.assertTrue((self.paths.needs_rendering / "high").is_dir())

    def test_claim_rechecks_blacklist_after_winning_rename(self) -> None:
        self._queue_job("race", priority=50, submitted_utc="2026-08-03T01:00:00.000Z")
        candidates_before_blacklist = list_job_candidates(self.paths)
        job_path = self.paths.needs_rendering / "race" / JOB_FILENAME
        job = read_json_object(job_path)
        job["blacklisted_workers"] = ["RENDER-RACE"]
        write_json_atomic(job_path, job)

        with patch(
            "portable_pipe_tools.render_farm.queue.list_job_candidates",
            return_value=candidates_before_blacklist,
        ):
            claimed = claim_next_job(self.paths, "RENDER-RACE")

        self.assertIsNone(claimed)
        self.assertTrue((self.paths.needs_rendering / "race").is_dir())
        self.assertEqual([], list(self.paths.is_rendering.iterdir()))

    def test_successful_simulation_updates_and_moves_job(self) -> None:
        create_test_job(self.farm_root)

        result = run_once(
            self.farm_root,
            "RENDER-03",
            simulate_success=True,
            minimum_stage_seconds=0.0,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        self.assertEqual(self.paths.render_complete, result.final_folder.parent)
        job = read_json_object(result.final_folder / JOB_FILENAME)
        result_json = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertEqual("complete", job["status"])
        self.assertEqual("RENDER-03", job["worker"])
        self.assertEqual(1, job["attempt"])
        self.assertEqual("complete", result_json["status"])
        self.assertEqual([], list(self.paths.is_rendering.iterdir()))

    def test_failed_simulation_blacklists_worker_and_requeues_job(self) -> None:
        queued_folder = create_test_job(self.farm_root)

        result = run_once(
            self.farm_root,
            "RENDER-04",
            simulate_success=False,
            minimum_stage_seconds=0.0,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("requeued", result.status)
        self.assertEqual(queued_folder, result.final_folder)
        self.assertEqual(self.paths.needs_rendering, result.final_folder.parent)
        job = read_json_object(result.final_folder / JOB_FILENAME)
        result_json = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertEqual("queued", job["status"])
        self.assertEqual(["RENDER-04"], job["blacklisted_workers"])
        self.assertIsNone(job["worker"])
        self.assertEqual(1, job["attempt"])
        self.assertEqual("failed", job["last_failure"]["status"])
        self.assertEqual(1, result_json["exit_code"])
        self.assertEqual("Simulated render failure", result_json["reason"])
        self.assertEqual([], list(self.paths.render_failed.iterdir()))

    def test_failures_accumulate_blacklist_until_another_worker_succeeds(self) -> None:
        queued_folder = create_test_job(self.farm_root)

        first_failure = run_once(
            self.farm_root,
            "RENDER-A",
            simulate_success=False,
            minimum_stage_seconds=0.0,
        )
        same_worker_retry = run_once(
            self.farm_root,
            "render-a",
            simulate_success=True,
            minimum_stage_seconds=0.0,
        )
        second_failure = run_once(
            self.farm_root,
            "RENDER-B",
            simulate_success=False,
            minimum_stage_seconds=0.0,
        )

        self.assertIsNotNone(first_failure)
        self.assertIsNone(same_worker_retry)
        self.assertIsNotNone(second_failure)
        retry_job = read_json_object(queued_folder / JOB_FILENAME)
        self.assertEqual(["RENDER-A", "RENDER-B"], retry_job["blacklisted_workers"])
        self.assertEqual(2, retry_job["attempt"])

        success = run_once(
            self.farm_root,
            "RENDER-C",
            simulate_success=True,
            minimum_stage_seconds=0.0,
        )

        self.assertIsNotNone(success)
        assert success is not None
        self.assertEqual("complete", success.status)
        completed_job = read_json_object(success.final_folder / JOB_FILENAME)
        self.assertEqual(["RENDER-A", "RENDER-B"], completed_job["blacklisted_workers"])
        self.assertEqual(3, completed_job["attempt"])

    def test_successful_real_runner_result_is_not_marked_simulated(self) -> None:
        create_test_job(self.farm_root)
        worker_uproject = self.farm_root / "worker" / "s3bishop.uproject"
        worker_uproject.parent.mkdir()
        worker_uproject.write_text("{}", encoding="utf-8")

        def successful_runner(**kwargs) -> UnrealExecutionResult:
            self.assertEqual("rendering", kwargs["job"]["status"])
            self.assertEqual(30.0, kwargs["timeout_seconds"])
            self.assertEqual(worker_uproject, kwargs["local_uproject"])
            return UnrealExecutionResult(
                success=True,
                reason="Real render completed",
                exit_code=0,
                unreal_result={
                    "success": True,
                    "stage": "render",
                    "output_file_count": 100,
                },
            )

        result = run_once(
            self.farm_root,
            "RENDER-REAL",
            simulate_success=False,
            minimum_stage_seconds=0.0,
            render_with_unreal=True,
            render_timeout_seconds=30.0,
            unreal_runner=successful_runner,
            local_uproject=worker_uproject,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("complete", result.status)
        result_json = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertFalse(result_json["simulated"])
        self.assertEqual(0, result_json["exit_code"])
        self.assertTrue(result_json["unreal_reported_success"])
        self.assertEqual(100, result_json["output_file_count"])

    def test_real_job_pulls_before_claim_and_records_latest_commit(self) -> None:
        queued_folder = create_test_job(self.farm_root)
        worker_uproject = self.farm_root / "worker" / "s3bishop.uproject"
        worker_uproject.parent.mkdir()
        worker_uproject.write_text("{}", encoding="utf-8")
        commit_before = "a" * 40
        commit_after = "b" * 40

        def successful_git_sync(project_directory: Path) -> GitPullResult:
            self.assertEqual(worker_uproject.parent, project_directory)
            self.assertTrue(queued_folder.is_dir())
            self.assertEqual([], list(self.paths.is_rendering.iterdir()))
            return GitPullResult(
                repository_root=worker_uproject.parent,
                branch="main",
                upstream="origin/main",
                commit_before=commit_before,
                commit_after=commit_after,
                summary="Fast-forward",
                transcript="$ git pull --ff-only\nFast-forward\n[exit code 0]\n",
            )

        def successful_runner(**kwargs) -> UnrealExecutionResult:
            self.assertFalse(queued_folder.exists())
            self.assertEqual(
                "latest_branch_git_pull_ff_only",
                kwargs["job"]["worker_sync_policy"],
            )
            self.assertEqual(commit_after, kwargs["job"]["git_commit_after_pull"])
            return UnrealExecutionResult(
                success=True,
                reason="Real render completed",
                exit_code=0,
                unreal_result={"success": True, "output_file_count": 1},
            )

        result = run_once(
            self.farm_root,
            "RENDER-GIT",
            simulate_success=False,
            minimum_stage_seconds=0.0,
            render_with_unreal=True,
            unreal_runner=successful_runner,
            local_uproject=worker_uproject,
            git_sync=successful_git_sync,
        )

        self.assertIsNotNone(result)
        assert result is not None
        job = read_json_object(result.final_folder / JOB_FILENAME)
        self.assertEqual("main", job["git_branch"])
        self.assertEqual("origin/main", job["git_upstream"])
        self.assertEqual(commit_after, job["rendered_git_commit"])
        self.assertTrue((result.final_folder / GIT_PULL_LOG_FILENAME).is_file())

    def test_git_pull_failure_leaves_job_queued(self) -> None:
        queued_folder = create_test_job(self.farm_root)
        worker_uproject = self.farm_root / "worker" / "s3bishop.uproject"
        worker_uproject.parent.mkdir()
        worker_uproject.write_text("{}", encoding="utf-8")

        def failed_git_sync(project_directory: Path) -> GitPullResult:
            self.assertEqual(worker_uproject.parent, project_directory)
            raise GitPullError("Git pull --ff-only failed")

        with self.assertRaisesRegex(GitPullError, "Git pull --ff-only failed"):
            run_once(
                self.farm_root,
                "RENDER-GIT-FAIL",
                simulate_success=False,
                minimum_stage_seconds=0.0,
                render_with_unreal=True,
                unreal_runner=lambda **kwargs: self.fail(
                    f"Render should not run: {kwargs}"
                ),
                local_uproject=worker_uproject,
                git_sync=failed_git_sync,
            )

        self.assertTrue(queued_folder.is_dir())
        self.assertEqual([], list(self.paths.is_rendering.iterdir()))
        self.assertEqual([], list(self.paths.render_failed.iterdir()))

    def test_real_runner_exception_blacklists_worker_and_requeues_job(self) -> None:
        create_test_job(self.farm_root)

        def broken_runner(**kwargs) -> UnrealExecutionResult:
            del kwargs
            raise FileNotFoundError("UnrealEditor-Cmd.exe")

        result = run_once(
            self.farm_root,
            "RENDER-BROKEN",
            simulate_success=False,
            minimum_stage_seconds=0.0,
            render_with_unreal=True,
            unreal_runner=broken_runner,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("requeued", result.status)
        self.assertEqual(self.paths.needs_rendering, result.final_folder.parent)
        job = read_json_object(result.final_folder / JOB_FILENAME)
        result_json = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertEqual(["RENDER-BROKEN"], job["blacklisted_workers"])
        self.assertFalse(result_json["simulated"])
        self.assertIsNone(result_json["exit_code"])
        self.assertIn("FileNotFoundError", result_json["reason"])

    def test_invalid_json_is_claimed_and_moved_to_failed(self) -> None:
        broken_folder = self.paths.needs_rendering / "broken-job"
        broken_folder.mkdir()
        (broken_folder / JOB_FILENAME).write_text("{broken", encoding="utf-8")

        result = run_once(
            self.farm_root,
            "RENDER-05",
            simulate_success=True,
            minimum_stage_seconds=0.0,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual("failed", result.status)
        self.assertTrue((result.final_folder / JOB_FILENAME).exists())
        failure = read_json_object(result.final_folder / RESULT_FILENAME)
        self.assertIn("invalid or unreadable", failure["reason"])

    def test_worker_reports_four_stages_with_five_second_minimums(self) -> None:
        create_test_job(self.farm_root)
        reported_stages: list[WorkerStage] = []
        sleep_durations: list[float] = []

        result = run_once(
            self.farm_root,
            "RENDER-06",
            simulate_success=True,
            minimum_stage_seconds=5.0,
            stage_callback=reported_stages.append,
            sleep=sleep_durations.append,
            monotonic=lambda: 0.0,
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            [
                WorkerStage.WAITING,
                WorkerStage.MOVING,
                WorkerStage.RENDERING,
                WorkerStage.FINISHING,
            ],
            reported_stages,
        )
        self.assertEqual([5.0, 5.0, 5.0, 5.0], sleep_durations)

    def test_worker_reports_claimed_job_details(self) -> None:
        create_test_job(
            self.farm_root,
            shot_name="SH090",
            render_version=7,
        )
        reported_jobs: list[dict] = []

        result = run_once(
            self.farm_root,
            "RENDER-DISPLAY",
            simulate_success=True,
            minimum_stage_seconds=0.0,
            job_callback=reported_jobs.append,
        )

        self.assertIsNotNone(result)
        self.assertEqual(1, len(reported_jobs))
        self.assertEqual("SH090", reported_jobs[0]["shot_name"])
        self.assertEqual(7, reported_jobs[0]["render_version"])
        self.assertEqual(
            "/Game/TEST/ReplaceWithRenderConfig",
            reported_jobs[0]["render_config"],
        )

    def test_stop_request_before_claim_leaves_job_queued(self) -> None:
        queued_folder = create_test_job(self.farm_root)
        reported_stages: list[WorkerStage] = []

        result = run_once(
            self.farm_root,
            "RENDER-STOPPING",
            simulate_success=True,
            minimum_stage_seconds=0.0,
            stage_callback=reported_stages.append,
            should_stop_before_claim=lambda: True,
        )

        self.assertIsNone(result)
        self.assertTrue(queued_folder.is_dir())
        self.assertEqual([WorkerStage.WAITING], reported_stages)

    def test_transient_windows_sharing_lock_is_retried(self) -> None:
        attempts = 0
        sleep_delays: list[float] = []

        def flaky_operation() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise self._windows_error(32)
            return "published"

        result = retry_transient_windows_lock(
            operation=flaky_operation,
            description="Publish test job",
            sleep=sleep_delays.append,
            monotonic=lambda: 0.0,
        )

        self.assertEqual("published", result)
        self.assertEqual(3, attempts)
        self.assertEqual([0.1, 0.2], sleep_delays)

    def test_non_transient_permission_error_is_not_retried(self) -> None:
        attempts = 0
        sleep_delays: list[float] = []

        def denied_operation() -> None:
            nonlocal attempts
            attempts += 1
            raise self._windows_error(5)

        with self.assertRaises(PermissionError):
            retry_transient_windows_lock(
                operation=denied_operation,
                description="Publish test job",
                sleep=sleep_delays.append,
                monotonic=lambda: 0.0,
            )

        self.assertEqual(1, attempts)
        self.assertEqual([], sleep_delays)

    def test_directory_rename_retries_dropbox_access_denied(self) -> None:
        source = self.paths.needs_rendering / "dropbox-rename-source"
        destination = self.paths.is_rendering / "dropbox-rename-destination"
        source.mkdir()
        original_rename = Path.rename
        attempts = 0

        def flaky_rename(path: Path, target: Path) -> Path:
            nonlocal attempts
            if path == source:
                attempts += 1
                if attempts == 1:
                    raise self._windows_error(5)
            return original_rename(path, target)

        with (
            patch.object(Path, "rename", new=flaky_rename),
            patch("portable_pipe_tools.render_farm.queue.time.sleep"),
        ):
            rename_path_with_retry(source, destination)

        self.assertEqual(2, attempts)
        self.assertFalse(source.exists())
        self.assertTrue(destination.is_dir())

    def test_transient_lock_retry_stops_at_timeout(self) -> None:
        clock_values = iter((0.0, 2.0))
        sleep_delays: list[float] = []

        with self.assertRaises(PermissionError):
            retry_transient_windows_lock(
                operation=lambda: self._raise_windows_error(32),
                description="Publish test job",
                timeout_seconds=1.0,
                sleep=sleep_delays.append,
                monotonic=lambda: next(clock_values),
            )

        self.assertEqual([], sleep_delays)

    def test_queue_folder_creation_retries_transient_lock(self) -> None:
        locked_farm_root = Path(self.temporary_directory.name) / "LockedRenderFarm"
        original_mkdir = Path.mkdir
        attempts = 0

        def flaky_mkdir(path: Path, *args: object, **kwargs: object) -> None:
            nonlocal attempts
            if path == locked_farm_root:
                attempts += 1
                if attempts == 1:
                    raise self._windows_error(32)
            original_mkdir(path, *args, **kwargs)

        with (
            patch.object(Path, "mkdir", new=flaky_mkdir),
            patch("portable_pipe_tools.render_farm.queue.time.sleep"),
        ):
            paths = create_queue_folders(locked_farm_root)

        self.assertEqual(2, attempts)
        self.assertTrue(paths.needs_rendering.is_dir())

    def test_json_read_retries_transient_lock(self) -> None:
        job_path = self.paths.needs_rendering / "read-retry.json"
        write_json_atomic(job_path, {"status": "queued"})
        original_open = Path.open
        attempts = 0

        def flaky_open(path: Path, *args: object, **kwargs: object):
            nonlocal attempts
            if path == job_path:
                attempts += 1
                if attempts == 1:
                    raise self._windows_error(32)
            return original_open(path, *args, **kwargs)

        with (
            patch.object(Path, "open", new=flaky_open),
            patch("portable_pipe_tools.render_farm.queue.time.sleep"),
        ):
            job = read_json_object(job_path)

        self.assertEqual(2, attempts)
        self.assertEqual("queued", job["status"])

    def test_queue_scan_retries_transient_lock(self) -> None:
        self._queue_job(
            "scan-retry",
            priority=50,
            submitted_utc="2026-08-03T02:00:00.000Z",
        )
        original_iterdir = Path.iterdir
        attempts = 0

        def flaky_iterdir(path: Path):
            nonlocal attempts
            if path == self.paths.needs_rendering:
                attempts += 1
                if attempts == 1:
                    raise self._windows_error(32)
            return original_iterdir(path)

        with (
            patch.object(Path, "iterdir", new=flaky_iterdir),
            patch("portable_pipe_tools.render_farm.queue.time.sleep"),
        ):
            candidates = list_job_candidates(self.paths)

        self.assertEqual(2, attempts)
        self.assertEqual(["scan-retry"], [candidate.folder.name for candidate in candidates])

    def test_temporary_json_write_and_cleanup_retry_transient_locks(self) -> None:
        output_path = self.paths.submitting / "atomic-retry.json"
        original_open = Path.open
        original_unlink = Path.unlink
        write_attempts = 0
        cleanup_attempts = 0

        def flaky_open(path: Path, *args: object, **kwargs: object):
            nonlocal write_attempts
            if path.name.startswith(f".{output_path.name}."):
                write_attempts += 1
                if write_attempts == 1:
                    raise self._windows_error(32)
            return original_open(path, *args, **kwargs)

        def flaky_unlink(path: Path, *args: object, **kwargs: object) -> None:
            nonlocal cleanup_attempts
            if path.name.startswith(f".{output_path.name}."):
                cleanup_attempts += 1
                if cleanup_attempts == 1:
                    raise self._windows_error(32)
            original_unlink(path, *args, **kwargs)

        with (
            patch.object(Path, "open", new=flaky_open),
            patch.object(Path, "unlink", new=flaky_unlink),
            patch("portable_pipe_tools.render_farm.queue.time.sleep"),
        ):
            write_json_atomic(output_path, {"status": "queued"})

        self.assertEqual(2, write_attempts)
        self.assertGreaterEqual(cleanup_attempts, 2)
        self.assertEqual("queued", read_json_object(output_path)["status"])

    def _queue_job(self, folder_name: str, priority: int, submitted_utc: str) -> None:
        folder = self.paths.needs_rendering / folder_name
        folder.mkdir()
        write_json_atomic(
            folder / JOB_FILENAME,
            {
                "schema_version": 1,
                "job_id": folder_name,
                "status": "queued",
                "priority": priority,
                "submitted_utc": submitted_utc,
                "attempt": 0,
            },
        )

    @staticmethod
    def _windows_error(winerror: int) -> PermissionError:
        error = PermissionError(13, "File is being used by another process")
        error.winerror = winerror
        return error

    @classmethod
    def _raise_windows_error(cls, winerror: int) -> None:
        raise cls._windows_error(winerror)


if __name__ == "__main__":
    unittest.main()
