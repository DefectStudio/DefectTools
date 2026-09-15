from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.apps.render_worker_v2_app import RenderWorkerV2App
from portable_pipe_tools.render_farm.v2_gui_settings import load_dropbox_root, save_unreal_editor_preference

MODULE = "portable_pipe_tools.apps.worker_project_list"


class WorkerFirstSetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        self.settings = self.path / "worker.json"
        save_unreal_editor_preference("", self.settings)
        self.app = RenderWorkerV2App(settings_path=self.settings)
        self.app.root.withdraw()
        self.addCleanup(lambda: self.app._shutdown_application(0))

    def assert_setup_locked(self):
        for name in ("worker_name_entry", "farm_root_entry", "browse_button", "local_uproject_entry",
                     "local_uproject_browse_button", "unreal_editor_cmd_entry", "unreal_editor_cmd_browse_button",
                     "poll_interval_spinbox", "render_timeout_spinbox", "simulate_result_combo",
                     "cloud_dispatcher_checkbutton", "connection_button", "check_setup_button",
                     "start_worker_button", "render_one_button", "stop_worker_button", "clear_log_button"):
            with self.subTest(control=name):
                self.assertEqual("disabled", str(getattr(self.app, name).cget("state")))
        widget = self.app.project_list
        self.assertFalse(widget.editing_enabled)
        self.assertEqual("disabled", str(widget.add_button.cget("state")))
        self.assertEqual("disabled", str(widget.remove_button.cget("state")))
        self.assertEqual("disabled", str(widget.root_refresh_button.cget("state")))
        self.assertTrue(widget.tree.instate(["disabled"]))
        self.assert_setup_visibility(False)

    def assert_setup_visibility(self, visible):
        self.assertEqual("grid" if visible else "", self.app.worker_name_entry.winfo_manager())
        self.assertEqual("grid" if visible else "", self.app.unreal_editor_cmd_entry.winfo_manager())
        self.assertEqual("grid" if visible else "", self.app.project_list.projects_frame.winfo_manager())
        self.assertEqual("grid" if visible else "", self.app.project_list.root_refresh_button.winfo_manager())
        self.assertEqual("pack" if visible else "", self.app.start_worker_button.master.winfo_manager())
        self.assertEqual("pack" if visible else "", self.app.animation_image_label.master.winfo_manager())
        self.assertEqual("pack" if visible else "", self.app.log_text.master.winfo_manager())
        self.assertEqual("grid", self.app.project_list.root_entry.winfo_manager())
        self.assertEqual("grid", self.app.project_list.root_browse_button.winfo_manager())

    def test_fresh_launch_only_allows_choosing_root(self):
        self.assert_setup_locked()
        self.assertEqual("normal", str(self.app.project_list.root_browse_button.cget("state")))
        self.assertIn("First", self.app.project_list.catalog_status.get())
        self.app.project_list.add()
        self.app._start_worker()
        self.app._render_registered_job()
        self.app._configure_connection()
        self.app._check_setup()
        self.assertIsNone(self.app.project_list.dialog)
        self.assertFalse(self.app._listener_state.active)
        self.assertFalse(self.app._busy)

    def test_browse_unlocks_immediately_and_persists_across_restart(self):
        root = self.path / "Dropbox"
        (root / "Show").mkdir(parents=True)
        with patch(MODULE + ".filedialog.askdirectory", return_value=str(root)):
            self.app.project_list._browse_dropbox()
        self.assertEqual(str(root), load_dropbox_root(self.settings))
        self.assertTrue(self.app.project_list.editing_enabled)
        self.assertEqual("normal", str(self.app.worker_name_entry.cget("state")))
        self.assertEqual("normal", str(self.app.start_worker_button.cget("state")))
        self.assertEqual("normal", str(self.app.check_setup_button.cget("state")))
        self.assertIn("1 Dropbox", self.app.project_list.catalog_status.get())
        self.assert_setup_visibility(True)
        self.app._set_busy(True, "Checking")
        self.assert_setup_visibility(True)
        self.app._set_busy(False, "Ready")
        self.app._shutdown_application(0)
        self.app = RenderWorkerV2App(settings_path=self.settings)
        self.app.root.withdraw()
        self.assertTrue(self.app.project_list.editing_enabled)
        self.assertEqual("normal", str(self.app.worker_name_entry.cget("state")))
        self.assert_setup_visibility(True)

        # Removing the root returns to first setup, and selecting it again restores the layout.
        self.app.project_list.dropbox_root.set("")
        self.assert_setup_visibility(False)
        self.app.project_list.dropbox_root.set(str(root))
        self.assert_setup_visibility(True)

    def test_cancel_or_invalid_folder_keeps_setup_locked(self):
        for selected in ("", str(self.path / "missing")):
            with patch(MODULE + ".filedialog.askdirectory", return_value=selected), \
                 patch(MODULE + ".messagebox.showerror"):
                self.app.project_list._browse_dropbox()
            self.assert_setup_locked()
            self.assertEqual("", load_dropbox_root(self.settings))

    def test_busy_lock_does_not_disable_root_forever_or_unlock_other_controls(self):
        self.app._set_busy(True, "Checking")
        self.assertEqual("disabled", str(self.app.project_list.root_browse_button.cget("state")))
        self.app._set_busy(False, "Ready")
        self.assertEqual("normal", str(self.app.project_list.root_browse_button.cget("state")))
        self.assert_setup_locked()
