from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from portable_pipe_tools.apps.render_worker_v2_app import RenderWorkerV2App
from portable_pipe_tools.render_farm.v2_gui_settings import load_dropbox_root, load_or_detect_unreal_editor, save_unreal_editor_preference

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
                     "unreal_editor_cmd_scan_button",
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

    def assert_setup_visibility(self, visible, root_is_set=None):
        if root_is_set is None:
            root_is_set = visible
        self.assertEqual("grid" if root_is_set else "", self.app.worker_name_entry.winfo_manager())
        self.assertEqual("grid" if root_is_set else "", self.app.engine_setup_frame.winfo_manager())
        self.assertEqual("grid" if visible else "", self.app.project_list.projects_frame.winfo_manager())
        self.assertEqual("grid" if root_is_set else "", self.app.project_list.root_refresh_button.winfo_manager())
        self.assertEqual("grid" if visible else "", self.app.farm_root_entry.winfo_manager())
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
        self.assert_setup_visibility(False, root_is_set=True)
        self.assertEqual("normal", str(self.app.unreal_editor_cmd_browse_button.cget("state")))
        engine = self.path / "UnrealEditor-Cmd.exe"
        engine.touch()
        with patch("portable_pipe_tools.apps.render_worker_v2_app.filedialog.askopenfilename", return_value=str(engine)):
            self.app._browse_unreal_editor_cmd()
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

    def test_unset_engine_keeps_lower_controls_hidden_and_actions_unavailable(self):
        self.app.project_list.dropbox_root.set(str(self.path))
        self.assert_setup_visibility(False, root_is_set=True)
        self.app.root.deiconify()
        self.app.root.update()
        self.assertTrue(self.app.unreal_editor_cmd_entry.winfo_viewable())
        self.assertTrue(self.app.unreal_editor_cmd_browse_button.winfo_viewable())
        self.assertFalse(self.app.project_list.tree.winfo_viewable())
        self.app.root.withdraw()
        with patch("portable_pipe_tools.apps.render_worker_v2_app.filedialog.askopenfilename", return_value=""):
            self.app._browse_unreal_editor_cmd()
        self.assert_setup_visibility(False, root_is_set=True)
        self.assertFalse(self.app.project_list.editing_enabled)
        self.app.project_list.add()
        self.app._start_worker()
        self.app._render_registered_job()
        self.app._configure_connection()
        self.app._check_setup()
        self.assertIsNone(self.app.project_list.dialog)
        self.assertFalse(self.app._listener_state.active)
        self.assertFalse(self.app._busy)

    def test_typing_and_clearing_engine_updates_visibility_and_saves_blank(self):
        with patch(MODULE + ".filedialog.askdirectory", return_value=str(self.path)):
            self.app.project_list._browse_dropbox()
        self.app.unreal_editor_cmd_var.set(str(self.path / "UnrealEditor-Cmd.exe"))
        self.assert_setup_visibility(True)
        self.app.root.update_idletasks()
        self.assertLess(self.app.unreal_editor_cmd_entry.winfo_rooty(),
                        self.app.project_list.projects_frame.winfo_rooty())
        self.app.unreal_editor_cmd_var.set("   ")
        self.assert_setup_visibility(False, root_is_set=True)
        self.assertEqual("normal", str(self.app.unreal_editor_cmd_entry.cget("state")))
        self.app._save_engine_field()
        self.app._shutdown_application(0)
        self.app = RenderWorkerV2App(settings_path=self.settings)
        self.app.root.withdraw()
        self.assert_setup_visibility(False, root_is_set=True)

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

    def wait_for_scan(self):
        deadline = time.monotonic() + 4
        while self.app._busy and time.monotonic() < deadline:
            self.app.root.update()
            time.sleep(0.01)
        self.assertFalse(self.app._busy)

    def test_scan_uses_existing_detector_and_saves_result(self):
        self.app.project_list.dropbox_root.set(str(self.path))
        detected = self.path / "UnrealEditor-Cmd.exe"
        with patch("portable_pipe_tools.apps.render_worker_v2_app.find_installed_unreal_editor", return_value=detected) as scan:
            self.app.unreal_editor_cmd_scan_button.invoke()
            self.assertEqual("disabled", str(self.app.unreal_editor_cmd_scan_button.cget("state")))
            self.wait_for_scan()
            scan.assert_called_once_with(["5.8"])
        self.assertEqual(str(detected), self.app.unreal_editor_cmd_var.get())
        self.assertEqual(str(detected), load_or_detect_unreal_editor(self.settings))
        self.assert_setup_visibility(True)
        self.assertEqual("normal", str(self.app.unreal_editor_cmd_scan_button.cget("state")))

    def test_unsuccessful_scan_preserves_existing_selection_and_allows_retry(self):
        self.app.project_list.dropbox_root.set(str(self.path))
        for current in ("", str(self.path / "Custom/UnrealEditor-Cmd.exe")):
            self.app.unreal_editor_cmd_var.set(current)
            with patch("portable_pipe_tools.apps.render_worker_v2_app.find_installed_unreal_editor", return_value=None):
                self.app.unreal_editor_cmd_scan_button.invoke()
                self.wait_for_scan()
            self.assertEqual(current, self.app.unreal_editor_cmd_var.get())
            self.assert_setup_visibility(bool(current), root_is_set=True)
            self.assertIn("No Unreal Engine 5.8", self.app.status_var.get())
            self.assertEqual("normal", str(self.app.unreal_editor_cmd_scan_button.cget("state")))

    def test_scan_is_blocked_until_root_and_recovers_from_errors(self):
        with patch("portable_pipe_tools.apps.render_worker_v2_app.find_installed_unreal_editor", side_effect=OSError("Scan unavailable")) as scan:
            self.app._scan_unreal_editor_cmd()
            scan.assert_not_called()
            self.app.project_list.dropbox_root.set(str(self.path))
            self.app.unreal_editor_cmd_scan_button.invoke()
            self.wait_for_scan()
        self.assertIn("scan failed", self.app.status_var.get())
        self.assert_setup_visibility(False, root_is_set=True)
        self.assertEqual("normal", str(self.app.unreal_editor_cmd_scan_button.cget("state")))
