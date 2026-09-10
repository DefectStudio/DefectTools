from pathlib import Path
import tempfile
import tkinter as tk
import unittest

from portable_pipe_tools.apps.worker_project_list import WorkerProjectList
from portable_pipe_tools.render_farm.v2_gui_settings import (
    load_dropbox_root, load_registered_projects, save_dropbox_root,
)


class WorkerDropboxTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        self.farm = self.path / "Dropbox/Development/renderFarm"
        self.farm.mkdir(parents=True)
        self.uproject = self.path / "DifferentUnrealName.uproject"
        self.uproject.write_text("{}")
        self.settings = self.path / "worker.json"
        save_dropbox_root(str(self.path / "Dropbox"), self.settings)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.widget = WorkerProjectList(self.root, settings_path=self.settings)

    def add_development(self):
        self.widget.add()
        dialog = self.widget.dialog
        self.assertEqual(("Development",), tuple(dialog.entries["project_id"].cget("values")))
        dialog.fields["project_id"].set("Development")
        dialog._select_show()
        dialog.fields["local_uproject"].set(str(self.uproject))
        dialog.save()

    def test_selection_maps_folder_name_and_path_and_survives_restart(self):
        self.add_development()
        project = load_registered_projects(self.settings)[0]
        self.assertEqual("Development", project.project_id)
        self.assertEqual("Development", project.name)
        self.assertEqual(str(self.farm), project.render_farm_root)
        self.assertFalse(project.allow_downloads)
        self.assertEqual(str(self.path / "Dropbox"), load_dropbox_root(self.settings))
        self.widget.destroy()
        self.widget = WorkerProjectList(self.root, settings_path=self.settings)
        self.assertEqual([project], self.widget.projects)
        # Removing a registration never removes the Dropbox show or Unreal project.
        self.widget.tree.selection_set("Development")
        self.widget.remove()
        self.assertEqual([], load_registered_projects(self.settings))
        self.assertTrue(self.farm.is_dir())
        self.assertTrue(self.uproject.is_file())

    def test_show_without_render_farm_can_be_selected_and_saved(self):
        show = self.path / "Dropbox/New Show"
        show.mkdir()
        self.widget.add()
        dialog = self.widget.dialog
        self.assertIn("New Show", dialog.entries["project_id"].cget("values"))
        dialog.fields["project_id"].set("New Show")
        dialog._select_show()
        dialog.fields["local_uproject"].set(str(self.uproject))
        dialog.save()
        project = load_registered_projects(self.settings)[0]
        self.assertEqual("New Show", project.project_id)
        self.assertEqual(str(show / "renderFarm"), project.render_farm_root)
        self.assertFalse((show / "renderFarm").exists())

    def test_offline_catalog_preserves_existing_registration_and_allows_edit(self):
        self.add_development()
        self.widget.dropbox_root.set(str(self.path / "unavailable"))
        self.widget.tree.selection_set("Development")
        self.widget.edit()
        dialog = self.widget.dialog
        self.assertIn("unavailable", self.widget.catalog_status.get())
        dialog.save()
        self.assertEqual("Development", load_registered_projects(self.settings)[0].project_id)

    def test_no_arbitrary_new_id_or_automatic_registration(self):
        self.assertEqual([], self.widget.projects)
        self.widget.add()
        dialog = self.widget.dialog
        dialog.fields["project_id"].set("invented")
        dialog.save()
        self.assertIn("Choose a project", dialog.error.get())
        self.assertEqual([], load_registered_projects(self.settings))
