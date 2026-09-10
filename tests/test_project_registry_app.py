import time
import tkinter as tk
import unittest
from unittest.mock import Mock

from portable_pipe_tools.apps.project_registry_app import ProjectRegistryWindow


class ProjectRegistryAppTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.client = Mock()
        self.client.list_projects.return_value = []
        self.window = ProjectRegistryWindow(self.root, client=self.client, can_manage=True)
        self.wait()

    def wait(self):
        deadline = time.monotonic() + 4
        while self.window.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.root.update()
        self.assertFalse(self.window.busy)

    def test_create_and_edit_use_server_results(self):
        created = dict(project_id="bishop", display_name="Bishop", active=True, revision=1)
        self.client.create_project.return_value = created
        self.window.add_button.invoke()
        editor = self.window.editor
        editor.project_id.set("bishop")
        editor.display_name.set("Bishop")
        self.client.list_projects.return_value = [created]
        editor.save_button.invoke()
        self.wait()
        self.client.create_project.assert_called_once_with("bishop", "Bishop", active=True)
        self.assertEqual(("bishop",), self.window.tree.get_children())
        self.window.tree.selection_set("bishop")
        self.window.edit()
        editor = self.window.editor
        self.assertEqual("readonly", str(editor.id_entry.cget("state")))
        editor.display_name.set("Bishop archived")
        editor.active.set(False)
        updated = dict(created, display_name="Bishop archived", active=False, revision=2)
        self.client.update_project.return_value = updated
        self.client.list_projects.return_value = [updated]
        editor.save_button.invoke()
        self.wait()
        self.client.update_project.assert_called_once_with("bishop", "Bishop archived", active=False, revision=1)
        self.assertEqual("No", self.window.tree.item("bishop", "values")[2])

    def test_failed_save_keeps_dialog_and_input(self):
        self.client.create_project.side_effect = RuntimeError("Project already exists")
        self.window.add()
        editor = self.window.editor
        editor.project_id.set("bishop")
        editor.display_name.set("Bishop")
        editor.save()
        self.wait()
        self.assertTrue(editor.winfo_exists())
        self.assertEqual("Bishop", editor.display_name.get())
        self.assertIn("already exists", editor.error.get())
        self.assertEqual((), self.window.tree.get_children())

    def test_read_only_window_cannot_create_or_edit(self):
        self.window.close()
        self.window = ProjectRegistryWindow(self.root, client=self.client, can_manage=False)
        self.wait()
        self.client.list_projects.assert_called_with(include_inactive=False)
        self.assertEqual("disabled", str(self.window.add_button.cget("state")))
        self.window.add()
        self.assertIsNone(self.window.editor)


if __name__ == "__main__":
    unittest.main()
