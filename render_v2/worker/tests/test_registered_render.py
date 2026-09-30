import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import Mock, patch

from portable_pipe_tools.render_farm import registered_render as renderer
from portable_pipe_tools.render_farm.project_registration import ProjectRegistration
from portable_pipe_tools.render_farm.project_workspace import project_lock, PreparationError
from portable_pipe_tools.render_farm.local_paths import prepare_worker_output_mapping
from portable_pipe_tools.render_farm.v2_gui_settings import save_registered_projects, save_unreal_editor_preference


class RegisteredRenderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.uproject = self.root / "CopiedProject/unrelated.uproject"
        self.uproject.parent.mkdir()
        self.uproject.write_text("{}")
        self.farm = self.root / "Dropbox/Show With Spaces/renderFarm"
        self.farm.mkdir(parents=True)
        self.engine = self.root / "Engine/UnrealEditor-Cmd.exe"
        self.engine.parent.mkdir()
        self.engine.write_bytes(b"test")
        self.settings = self.root / "worker.json"
        self.registration = ProjectRegistration.from_dict(dict(
            project_id="Show With Spaces", name="Show With Spaces",
            local_uproject=str(self.uproject), render_farm_root=str(self.farm)))
        save_registered_projects([self.registration], self.settings)
        save_unreal_editor_preference(str(self.engine), self.settings)
        self.job = self.root / "job.json"
        self.data = dict(project_id="Show With Spaces", shot_name="ZZZ_000_0850",
                         job_id="source_job", status="queued", job_type="unreal_movie_render_graph",
                         uproject="X:/OtherMachine/Other.uproject", level="/Game/Map", sequence="/Game/Sequence",
                         render_config="/Game/Graph", output_directory="X:/OldOutput",
                         output_relative_directory="old/output", worker_sync_policy="managed_project_fetch",
                         prepared_git_commit="obsolete", frame_count=40, outputs={"exr": True, "mp4": False},
                         graph_variable_overrides={"OutputDirectory": {"enabled": True, "serialized_value": "old"},
                                                   "FileNameFormat": {"enabled": True, "serialized_value": "old"}})
        self.job.write_text(json.dumps(self.data))
        self.result = Mock(success=True, reason="Rendered", cancelled=False)
        self.result.terminal_result_details.return_value = {"frame_count": 40}
        self.sync = self.enterContext(patch.object(renderer, "sync_registered_project", return_value="a" * 40))

    def render(self, **kwargs):
        return renderer.render_registered_job(self.settings, "Show With Spaces", self.job,
                                               progress=lambda _: None, **kwargs)

    def test_updated_project_renders_and_preserves_input(self):
        before = self.job.read_bytes()
        with patch.object(renderer.shutil, "which", return_value=None), \
             patch.object(renderer.subprocess, "run", side_effect=AssertionError("No Git required")), \
             patch.object(renderer, "execute_unreal_job", return_value=self.result) as execute:
            first = self.render()
            second = self.render()
        self.assertTrue(first["success"])
        self.assertNotEqual(first["run_root"], second["run_root"])
        job = execute.call_args.args[1]
        self.assertEqual(str(self.uproject), job["uproject"])
        self.assertEqual("latest_branch_git_pull_ff_only", job["worker_sync_policy"])
        self.assertEqual("a" * 40, job["prepared_git_commit"])
        self.assertEqual(2, self.sync.call_count)
        self.assertEqual("output", job["output_relative_directory"])
        self.assertEqual(before, self.job.read_bytes())
        self.assertTrue((self.uproject.parent / "Plugins/RenderWorkerRuntime/.render-worker-runtime").is_file())
        self.assertTrue((Path(first["run_root"]) / "result.json").is_file())
        mapping = prepare_worker_output_mapping(job, execute.call_args.kwargs["render_farm_root"])
        self.assertEqual(Path(second["run_root"]) / "output", mapping.worker_output_directory)

    def test_wrong_or_unregistered_project_fails_before_runtime_install(self):
        with patch.object(renderer, "install_runtime") as install:
            with self.assertRaisesRegex(ValueError, "not registered"):
                renderer.render_registered_job(self.settings, "Unknown", self.job)
            self.data["project_id"] = "DifferentShow"
            self.job.write_text(json.dumps(self.data))
            with self.assertRaisesRegex(ValueError, "does not match"):
                self.render()
            install.assert_not_called()

    def test_existing_checkout_updates_even_with_clone_downloads_off(self):
        subprocess.run(["git", "init", str(self.uproject.parent)], check=True, capture_output=True)
        real_run = subprocess.run
        commands = []
        def local_git_only(args, **kwargs):
            commands.append(args)
            self.assertEqual(["git", "rev-parse"], args[:2])
            return real_run(args, **kwargs)
        with patch.object(renderer.subprocess, "run", side_effect=local_git_only), \
             patch.object(renderer, "execute_unreal_job", return_value=self.result):
            self.render()
        self.assertGreaterEqual(len(commands), 2)
        self.assertFalse(self.registration.allow_downloads)
        self.sync.assert_called_once()
        self.assertIn("/Plugins/RenderWorkerRuntime/", (self.uproject.parent / ".git/info/exclude").read_text())

    def test_sync_failure_never_installs_runtime_or_starts_unreal(self):
        self.sync.side_effect = PreparationError("Git LFS download failed")
        with patch.object(renderer, "install_runtime") as install, patch.object(renderer, "execute_unreal_job") as execute:
            with self.assertRaisesRegex(PreparationError, "Git LFS"):
                self.render()
            install.assert_not_called()
            execute.assert_not_called()

    def test_missing_local_project_never_falls_back_to_a_download(self):
        self.uproject.unlink()
        with patch.object(renderer.subprocess, "run", side_effect=AssertionError("No Git allowed")):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                self.render()

    def test_missing_engine_is_rejected_without_detecting_another(self):
        self.engine.unlink()
        with self.assertRaisesRegex(ValueError, "UnrealEditor-Cmd"):
            self.render()

    def test_cancelled_before_start_does_not_install_or_launch(self):
        with patch.object(renderer, "install_runtime") as install:
            with self.assertRaises(renderer.PreparationCancelled):
                self.render(cancelled=lambda: True)
            install.assert_not_called()

    def test_lock_prevents_second_worker_using_same_local_project(self):
        with patch.object(renderer.shutil, "which", return_value=None):
            with project_lock(renderer.local_project_lock(self.uproject)):
                with self.assertRaises(PreparationError):
                    self.render()

    def test_failure_writes_receipt_and_releases_lock(self):
        with patch.object(renderer.shutil, "which", return_value=None), \
             patch.object(renderer, "install_runtime"), \
             patch.object(renderer, "execute_unreal_job", side_effect=RuntimeError("Unreal failed")):
            with self.assertRaisesRegex(RuntimeError, "Unreal failed"):
                self.render()
            receipts = list((self.farm.parent / "WorkerV2Renders").rglob("result.json"))
            self.assertEqual(1, len(receipts))
            self.assertFalse(json.loads(receipts[0].read_text())["success"])
            with project_lock(renderer.local_project_lock(self.uproject)):
                pass

    def test_cancel_callback_and_timeout_reach_executor(self):
        cancelled = Mock(return_value=False)
        with patch.object(renderer, "install_runtime"), \
             patch.object(renderer, "execute_unreal_job", return_value=self.result) as execute:
            self.render(timeout_seconds=60, cancelled=cancelled)
        self.assertIs(cancelled, execute.call_args.kwargs["should_cancel"])
        self.assertEqual(60, execute.call_args.kwargs["timeout_seconds"])
