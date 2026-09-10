import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.render_farm.registered_claims import RegisteredQueueWorker
from portable_pipe_tools.render_farm.project_registration import ProjectRegistration
from portable_pipe_tools.render_farm.queue import create_queue_folders, write_json_atomic
from portable_pipe_tools.render_farm.unreal_runner import UnrealExecutionResult
from portable_pipe_tools.render_farm.v2_gui_settings import save_registered_projects, save_unreal_editor_preference
from portable_pipe_tools.render_farm.cloud_dispatch import CloudClaimResult, CloudJobLease


class RegisteredClaimTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.settings = self.root / "worker.json"
        self.engine = self.root / "UnrealEditor-Cmd.exe"
        self.engine.write_bytes(b"test")
        self.projects = []
        for name in ["Bishop", "Spectrum"]:
            uproject = self.root / name / f"{name}.uproject"
            uproject.parent.mkdir()
            uproject.write_text("{}")
            farm = self.root / "Dropbox" / name / "renderFarm"
            create_queue_folders(farm)
            self.projects.append(ProjectRegistration.from_dict(dict(
                project_id=name, name=name, local_uproject=str(uproject), render_farm_root=str(farm))))
        save_registered_projects(self.projects, self.settings)
        save_unreal_editor_preference(str(self.engine), self.settings)
        self.executor = Mock(return_value=UnrealExecutionResult(True, "Rendered", 0))
        self.worker = RegisteredQueueWorker(self.settings, "TestWorker", progress=lambda _: None, executor=self.executor)

    def job(self, folder_project, identity, identifier, priority=50):
        farm = Path(folder_project.render_farm_root)
        folder = farm / "01_NeedsRendering" / identifier
        folder.mkdir()
        job = dict(schema_version=1, job_id=identifier, project=identity, job_type="unreal_movie_render_graph",
                   status="queued", priority=priority, submitted_utc="2026-09-10T00:00:00Z", shot_name="SHOT_001",
                   uproject="X:/OtherMachine/show.uproject", level="/Game/Map", sequence="/Game/Seq",
                   render_config="/Game/Graph", output_directory=str(farm.parent / identifier),
                   output_relative_directory=identifier, outputs={"exr": True, "mp4": False},
                   graph_variable_overrides={"OutputDirectory": {"enabled": True, "serialized_value": "old"},
                                             "FileNameFormat": {"enabled": True, "serialized_value": "SHOT.{frame_number}"}})
        write_json_atomic(folder / "job.json", job)
        return folder

    def test_worker_claims_highest_priority_eligible_show_and_finishes_it(self):
        self.job(self.projects[0], "Bishop", "bishop", priority=20)
        high = self.job(self.projects[1], "Spectrum", "spectrum", priority=90)
        unrelated = self.job(self.projects[0], "Unregistered", "other", priority=100)
        with patch("portable_pipe_tools.render_farm.registered_claims.install_runtime"), \
             patch("portable_pipe_tools.render_farm.worker.pull_latest_branch", side_effect=AssertionError("No Git updates")):
            result = self.worker.run_next()
        self.assertEqual("complete", result.status)
        self.assertFalse(high.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(Path(self.projects[1].local_uproject), self.executor.call_args.kwargs["local_uproject"])
        self.assertEqual("registered_local_only", self.executor.call_args.kwargs["job"]["worker_sync_policy"])

    def test_unavailable_registered_project_is_not_claimed(self):
        queued = self.job(self.projects[0], "Bishop", "bishop")
        Path(self.projects[0].local_uproject).unlink()
        self.assertIsNone(self.worker.run_next())
        self.assertTrue(queued.exists())
        self.executor.assert_not_called()

    def test_stop_before_claim_preserves_queue(self):
        queued = self.job(self.projects[0], "Bishop", "bishop")
        self.assertIsNone(self.worker.run_next(stopped=lambda: True))
        self.assertTrue(queued.exists())

    def test_failure_requeues_and_blacklists_in_v1_flow(self):
        self.job(self.projects[0], "Bishop", "bishop")
        self.executor.return_value = UnrealExecutionResult(False, "Unreal failed", 1)
        with patch("portable_pipe_tools.render_farm.registered_claims.install_runtime"):
            result = self.worker.run_next()
        self.assertEqual("requeued", result.status)
        self.assertTrue(result.final_folder.is_dir())

    def test_cloud_request_advertises_available_projects_and_resolves_job_paths(self):
        dispatcher = Mock()
        worker = RegisteredQueueWorker(self.settings, "TestWorker", dispatcher_client=dispatcher, progress=lambda _: None)
        with patch("portable_pipe_tools.render_farm.registered_claims.run_once") as run:
            worker.run_next()
        kwargs = run.call_args.kwargs
        self.assertEqual(["Bishop", "Spectrum"], kwargs["eligible_project_ids"])
        farm, uproject = kwargs["job_paths_resolver"]({"project": "spectrum"})
        self.assertEqual(Path(self.projects[1].render_farm_root), farm)
        self.assertEqual(Path(self.projects[1].local_uproject), uproject)
        self.assertIsNone(kwargs["git_sync"])

    def test_cloud_claim_renders_nonfirst_show_renews_lease_and_reports_completion(self):
        folder = self.job(self.projects[1], "Spectrum", "cloud_spectrum")
        job = json.loads((folder / "job.json").read_text())
        job.update(status="rendering", attempt=1, worker="TestWorker", lease_token="local-lease")
        dispatcher = Mock()
        dispatcher.claim_job.return_value = CloudClaimResult(
            lease=CloudJobLease(job=job, lease_token="local-lease", lease_expires_at=int(time.time()) + 300, stop_requested=False),
            stop_requested=False)
        dispatcher.heartbeat_job.return_value = {"lease_expires_at": int(time.time()) + 300}
        def render(**kwargs):
            self.assertFalse(kwargs["should_cancel"]())
            self.assertEqual(Path(self.projects[1].render_farm_root), kwargs["render_farm_root"])
            self.assertEqual(Path(self.projects[1].local_uproject), kwargs["local_uproject"])
            return UnrealExecutionResult(True, "Rendered Spectrum", 0)
        worker = RegisteredQueueWorker(self.settings, "TestWorker", dispatcher_client=dispatcher,
                                       progress=lambda _: None, executor=render)
        with patch("portable_pipe_tools.render_farm.registered_claims.install_runtime"):
            result = worker.run_next(heartbeat_interval_seconds=0.000001)
        self.assertEqual("complete", result.status)
        self.assertEqual("cloud_spectrum", dispatcher.complete_job.call_args.args[0])
        dispatcher.heartbeat_job.assert_called()

    def test_ineligible_cloud_response_is_released_before_rendering(self):
        dispatcher = Mock()
        dispatcher.claim_job.return_value = CloudClaimResult(
            lease=CloudJobLease(job={"job_id": "other", "project": "UnknownShow"}, lease_token="lease",
                               lease_expires_at=int(time.time()) + 300, stop_requested=False), stop_requested=False)
        worker = RegisteredQueueWorker(self.settings, "TestWorker", dispatcher_client=dispatcher,
                                       progress=lambda _: None, executor=self.executor)
        with self.assertRaisesRegex(ValueError, "ineligible"):
            worker.run_next()
        dispatcher.release_job.assert_called_once()
        self.executor.assert_not_called()

    def test_empty_ready_list_still_checks_cloud_stop_without_claiming_other_shows(self):
        dispatcher = Mock()
        dispatcher.claim_job.return_value = CloudClaimResult(lease=None, stop_requested=True)
        worker = RegisteredQueueWorker(self.settings, "TestWorker", dispatcher_client=dispatcher, progress=lambda _: None)
        for project in self.projects:
            Path(project.local_uproject).unlink()
        result = worker.run_next()
        self.assertEqual("stopped", result.status)
        self.assertEqual([], dispatcher.claim_job.call_args.kwargs["eligible_project_ids"])
        dispatcher.acknowledge_worker_stop.assert_called_once()
