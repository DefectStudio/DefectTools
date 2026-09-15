from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from portable_pipe_tools.apps.render_worker_v2_app import RenderWorkerV2App
from portable_pipe_tools.render_farm.project_registration import ProjectRegistration
from portable_pipe_tools.render_farm.v2_gui_settings import save_registered_projects, save_unreal_editor_preference, load_listener_preferences


MODULE = "portable_pipe_tools.apps.render_worker_v2_app"


class RegisteredRenderGuiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        self.settings = self.path / "worker.json"
        save_unreal_editor_preference("", self.settings)
        registration = ProjectRegistration.from_dict(dict(project_id="Show", name="Show",
            local_uproject=str(self.path / "Show.uproject"), render_farm_root=str(self.path / "Show/renderFarm")))
        save_registered_projects([registration], self.settings)
        self.app = RenderWorkerV2App(settings_path=self.settings)
        self.app.root.withdraw()
        self.addCleanup(lambda: None if self.app._closing else self.app._shutdown_application(0))
        self.app.project_list.tree.selection_set("Show")

    def wait_finished(self):
        deadline = time.monotonic() + 4
        while self.app._busy and time.monotonic() < deadline:
            self.app.root.update()
            time.sleep(0.01)
        self.assertFalse(self.app._busy)

    def test_selected_registration_drives_async_render_and_controls_recover(self):
        result = dict(success=True, reason="40 frames", run_root=str(self.path))
        with patch(MODULE + ".filedialog.askopenfilename", return_value=str(self.path / "job.json")), \
             patch(MODULE + ".render_registered_job", return_value=result) as render:
            self.app._render_registered_job()
            self.assertFalse(self.app.project_list.editing_enabled)
            self.assertEqual("disabled", str(self.app.render_one_button.cget("state")))
            self.wait_finished()
        self.assertEqual("Show", render.call_args.args[1])
        self.assertEqual(self.settings, render.call_args.args[0])
        self.assertTrue(self.app.project_list.editing_enabled)
        self.assertEqual("normal", str(self.app.render_one_button.cget("state")))
        self.assertEqual("normal", str(self.app.start_worker_button.cget("state")))
        self.assertEqual("Render complete", self.app.status_var.get())

    def test_setup_check_is_async_and_does_not_start_listener(self):
        from portable_pipe_tools.render_farm.worker_setup import SetupReport
        self.app.use_cloud_dispatcher_var.set(False)
        with patch(MODULE + ".check_worker_setup", return_value=SetupReport(projects=["Show"])) as check, \
             patch(MODULE + ".messagebox.showinfo"), patch(MODULE + ".RegisteredQueueWorker") as worker:
            self.app._check_setup()
            self.assertFalse(self.app.project_list.editing_enabled)
            self.wait_finished()
            self.assertEqual("Setup checks passed", self.app.status_var.get())
            check.assert_called_once_with(self.settings, dispatcher=None)
            worker.assert_not_called()
            self.assertFalse(self.app._listener_state.active)

    def test_stop_cancels_active_render_and_preserves_registration(self):
        started = threading.Event()
        def render(*args, cancelled, **kwargs):
            started.set()
            deadline = time.monotonic() + 3
            while not cancelled() and time.monotonic() < deadline:
                time.sleep(0.01)
            return dict(success=False, reason="Cancelled", run_root=str(self.path))
        with patch(MODULE + ".filedialog.askopenfilename", return_value=str(self.path / "job.json")), \
             patch(MODULE + ".render_registered_job", side_effect=render):
            self.app._render_registered_job()
            self.assertTrue(started.wait(1))
            self.app.project_list.remove()
            self.assertEqual(1, len(self.app.project_list.projects))
            self.app._stop_worker()
            self.assertTrue(self.app._registered_render_cancel.is_set())
            self.wait_finished()
        self.assertFalse(self.app._registered_render_active)
        self.assertEqual("Cancelled", self.app.status_var.get())

    def test_start_polls_registered_projects_without_legacy_paths_or_git_updater(self):
        engine = self.path / "UnrealEditor-Cmd.exe"
        engine.write_bytes(b"test")
        self.app.unreal_editor_cmd_var.set(str(engine))
        self.app.worker_name_var.set("V2-Test")
        self.app.farm_root_var.set("invalid unused legacy path")
        self.app.use_cloud_dispatcher_var.set(False)
        service = Mock()
        service.projects = self.app.project_list.projects
        service.run_next.return_value = None
        heartbeat = Mock()
        heartbeat.poll_remote_stop.return_value = False
        heartbeat.remote_stop_event.is_set.return_value = False
        heartbeat.pop_errors.return_value = []
        with patch(MODULE + ".RegisteredQueueWorker", return_value=service) as factory, \
             patch(MODULE + ".WorkerHeartbeat", return_value=heartbeat), \
             patch.object(self.app, "_schedule_periodic_update_check") as updater:
            self.app._start_worker()
            self.assertTrue(self.app._listener_state.active)
            self.assertFalse(self.app.project_list.editing_enabled)
            deadline = time.monotonic() + 3
            while (not service.run_next.called or self.app._busy) and time.monotonic() < deadline:
                self.app.root.update()
                time.sleep(0.01)
            service.run_next.assert_called_once()
            factory.assert_called_once()
            updater.assert_not_called()
            self.app._stop_worker()
            self.assertFalse(self.app._listener_state.active)
        self.assertTrue(self.app.project_list.editing_enabled)
        self.assertEqual("V2-Test", load_listener_preferences(self.settings)["worker_name"])
