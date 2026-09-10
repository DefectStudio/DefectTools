from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.project_discovery import editor_project_candidates


class EditorProjectDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.metadata = self.root / "LocalAppData"

    def project(self, name, nested=False):
        root = self.root / name
        (root / ".git").mkdir(parents=True)
        project = root / ("Game/Sample.uproject" if nested else "Sample.uproject")
        project.parent.mkdir(parents=True, exist_ok=True)
        project.write_text("{}")
        return root, project

    def editor(self, version, lines, encoding="utf-8"):
        path = self.metadata / f"UnrealEngine/{version}/Saved/Config/WindowsEditor/EditorSettings.ini"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[/Script/UnrealEd.EditorSettings]\n" + lines, encoding=encoding)
        return path

    def test_recent_projects_across_versions_are_sorted_and_nested_repos_resolved(self):
        older, old_project = self.project("older")
        newer, new_project = self.project("newer", nested=True)
        self.editor("5.7", f'RecentlyOpenedProjectFiles=(ProjectName="{new_project.as_posix()}",LastOpenTime=2026.09.10-10.00.00)\n', "utf-16")
        self.editor("5.8", f'RecentlyOpenedProjectFiles=(ProjectName="{old_project.as_posix()}",LastOpenTime=2026.09.09-10.00.00)\n'
                            f'RecentlyOpenedProjectFiles=(ProjectName="{new_project.as_posix()}",LastOpenTime=2026.09.10-10.00.00)\n'
                            f'RecentlyOpenedProjectFiles="{self.root.as_posix()}/missing.uproject"\n')
        self.assertEqual([newer, older], list(editor_project_candidates(self.metadata)))

    def test_launcher_repeated_roots_and_legacy_editor_paths_are_discovered(self):
        first, project = self.project("first")
        second, _ = self.project("library/second")
        self.editor("5.1", f'RecentlyOpenedProjectFiles="{project.as_posix()}"\n')
        launcher = self.metadata / "EpicGamesLauncher/Saved/Config/Windows/GameUserSettings.ini"
        launcher.parent.mkdir(parents=True)
        launcher.write_text(f'[Launcher]\nCreatedProjectPaths={self.root / "library"}\nCreatedProjectPaths={first}\n')
        self.assertEqual([first, second], list(editor_project_candidates(self.metadata)))

    def test_metadata_is_reread_and_unrelated_sections_and_removed_entries_are_ignored(self):
        first, project = self.project("first")
        second, second_project = self.project("second")
        path = self.editor("5.8", f'CreatedProjectPaths={first}\n!CreatedProjectPaths=ClearArray\n'
                                   f'+RecentlyOpenedProjectFiles="{project.as_posix()}"\n'
                                   f'-RecentlyOpenedProjectFiles="{project.as_posix()}"\n'
                                   f'[Unrelated]\nCreatedProjectPaths={second}\n')
        self.assertEqual([], list(editor_project_candidates(self.metadata)))
        path = self.editor("5.8", f'RecentlyOpenedProjectFiles="{second_project.as_posix()}"\n')
        before = path.read_bytes()
        self.assertEqual([second], list(editor_project_candidates(self.metadata)))
        self.assertEqual(before, path.read_bytes())

    def test_missing_malformed_and_excluded_metadata_candidates_do_not_block_discovery(self):
        self.assertEqual([], list(editor_project_candidates(self.metadata)))
        root, project = self.project("excluded")
        self.editor("5.8", f'RecentlyOpenedProjectFiles=(broken)\nCreatedProjectPaths=relative/path\n'
                            f'RecentlyOpenedProjectFiles="{project.as_posix()}"\n')
        self.assertEqual([], list(editor_project_candidates(self.metadata, excluded=(root,))))


if __name__ == "__main__":
    unittest.main()
