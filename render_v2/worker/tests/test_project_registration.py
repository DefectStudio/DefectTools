import json
from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.project_registration import ProjectRegistration
from portable_pipe_tools.render_farm.v2_gui_settings import (
    load_registered_projects, save_registered_projects, save_unreal_editor_preference,
)


class ProjectRegistrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.settings = self.root / "worker_v2.json"
        self.project = self.root / "Show/show.uproject"
        self.project.parent.mkdir()
        self.project.write_text("{}")
        self.farm = self.root / "Output/RenderFarm"
        self.farm.mkdir(parents=True)
        self.values = dict(project_id="show", name="Show", local_uproject=str(self.project),
                           render_farm_root=str(self.farm))

    def test_new_registration_defaults_to_downloads_off(self):
        project = ProjectRegistration.from_dict(self.values)
        self.assertFalse(project.allow_downloads)
        self.assertEqual("Local paths available", project.location_status())

    def test_add_edit_and_remove_persist_without_touching_project_files(self):
        save_unreal_editor_preference("D:/Engine/UnrealEditor-Cmd.exe", self.settings)
        save_registered_projects([ProjectRegistration.from_dict(self.values)], self.settings)
        self.assertEqual("Show", load_registered_projects(self.settings)[0].name)
        edited = ProjectRegistration.from_dict(dict(self.values, name="Renamed show"))
        save_registered_projects([edited], self.settings)
        self.assertEqual("Renamed show", load_registered_projects(self.settings)[0].name)
        save_registered_projects([], self.settings)
        self.assertEqual([], load_registered_projects(self.settings))
        self.assertEqual("{}", self.project.read_text())
        self.assertTrue(self.farm.is_dir())
        self.assertEqual("D:/Engine/UnrealEditor-Cmd.exe", json.loads(self.settings.read_text())["unreal_editor_cmd"])

    def test_duplicate_ids_rejected_without_overwriting_saved_list(self):
        project = ProjectRegistration.from_dict(self.values)
        save_registered_projects([project], self.settings)
        with self.assertRaisesRegex(ValueError, "already registered"):
            save_registered_projects([project, project], self.settings)
        self.assertEqual([project], load_registered_projects(self.settings))

    def test_download_permission_requires_repository_and_branch(self):
        with self.assertRaises(ValueError):
            ProjectRegistration.from_dict(dict(self.values, allow_downloads=True))
        with self.assertRaises(ValueError):
            ProjectRegistration.from_dict(dict(self.values, allow_downloads=True,
                                               repository="https://example.com/studio/show.git", branch="../bad"))
        project = ProjectRegistration.from_dict(dict(self.values, allow_downloads=True,
                                                     repository="https://example.com/studio/show.git", branch="main"))
        save_registered_projects([project], self.settings)
        self.assertTrue(load_registered_projects(self.settings)[0].allow_downloads)

    def test_folder_names_preserve_case_and_spaces_but_reject_case_duplicates(self):
        project = ProjectRegistration.from_dict(dict(self.values, project_id="Show With Spaces"))
        save_registered_projects([project], self.settings)
        self.assertEqual("Show With Spaces", load_registered_projects(self.settings)[0].project_id)
        duplicate = ProjectRegistration.from_dict(dict(self.values, project_id="show with spaces"))
        with self.assertRaisesRegex(ValueError, "already registered"):
            save_registered_projects([project, duplicate], self.settings)
        self.assertEqual([project], load_registered_projects(self.settings))

    def test_missing_local_file_is_reported_without_losing_registration(self):
        self.values["local_uproject"] = str(self.root / "Missing/show.uproject")
        project = ProjectRegistration.from_dict(self.values)
        save_registered_projects([project], self.settings)
        self.assertEqual("Missing project", load_registered_projects(self.settings)[0].location_status())

    def test_invalid_project_paths_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "uproject"):
            ProjectRegistration.from_dict(dict(self.values, local_uproject="relative.uproject"))
        with self.assertRaisesRegex(ValueError, "RenderFarm"):
            ProjectRegistration.from_dict(dict(self.values, render_farm_root=str(self.root / "Other")))


if __name__ == "__main__":
    unittest.main()
