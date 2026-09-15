from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm import engine_discovery as discovery
from portable_pipe_tools.render_farm.unreal_runner import resolve_unreal_editor_cmd


class EngineDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.program_data = self.root / "ProgramData"
        self.program_files = self.root / "ProgramFiles"
        self.manifest = self.program_data / "Epic/UnrealEngineLauncher/LauncherInstalled.dat"
        self.manifest.parent.mkdir(parents=True)
        self.enterContext(patch.dict("os.environ", {
            "ProgramData": str(self.program_data),
            "ProgramFiles": str(self.program_files),
        }))
        self.registry = self.enterContext(patch.object(discovery, "_registry_installations", return_value=[]))

    def install(self, root: Path, version: tuple[int, int] = (5, 8)) -> Path:
        executable = root / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"test executable; never launched")
        metadata = root / "Engine/Build/Build.version"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(json.dumps({"MajorVersion": version[0], "MinorVersion": version[1]}))
        return executable

    def launcher(self, *entries: tuple[str, Path]) -> None:
        self.manifest.write_text(json.dumps({"InstallationList": [
            {"AppName": name, "InstallLocation": str(root)} for name, root in entries
        ]}))

    def test_launcher_install_on_nonstandard_drive_is_used_by_runner(self) -> None:
        root = self.root / "Custom drive/Unreal Engine/5.8"
        expected = self.install(root)
        self.launcher(("UE_5.8", root))
        project = self.root / "project.uproject"
        project.write_text(json.dumps({"EngineAssociation": "5.8"}))
        self.assertEqual(expected, resolve_unreal_editor_cmd({"uproject": str(project)}))

    def test_project_version_wins_over_submitted_version(self) -> None:
        newer, older = self.root / "5.8", self.root / "5.7"
        expected = self.install(newer)
        self.install(older, (5, 7))
        self.launcher(("UE_5.7", older), ("UE_5.8", newer))
        self.assertEqual(expected, discovery.find_installed_unreal_editor(["5.8", "5.7"]))

    def test_stale_launcher_entry_is_skipped(self) -> None:
        valid = self.root / "valid"
        expected = self.install(valid)
        self.launcher(("UE_5.8", self.root / "removed"), ("UE_5.8", valid))
        self.assertEqual(expected, discovery.find_installed_unreal_editor(["5.8"]))

    def test_wrong_build_version_is_not_selected(self) -> None:
        root = self.root / "stale-registration"
        self.install(root, (5, 7))
        self.launcher(("UE_5.8", root))
        self.assertIsNone(discovery.find_installed_unreal_editor(["5.8"]))

    def test_registry_install_is_used_when_launcher_manifest_is_invalid(self) -> None:
        root = self.root / "registered"
        expected = self.install(root)
        self.registry.return_value = [discovery.EngineInstallation("5.8", root)]
        self.manifest.write_text("invalid JSON")
        self.assertEqual(expected, discovery.find_installed_unreal_editor(["5.8"]))

    def test_malformed_launcher_data_is_ignored(self) -> None:
        for document in [[], {"InstallationList": None}, {"InstallationList": [None, {}, {"AppName": 8}]}]:
            with self.subTest(document=document):
                self.manifest.write_text(json.dumps(document))
                self.assertIsNone(discovery.find_installed_unreal_editor(["5.8"]))

    def test_named_build_is_selected_instead_of_launcher_version(self) -> None:
        normal, custom = self.root / "launcher", self.root / "custom"
        self.install(normal)
        expected = self.install(custom)
        self.launcher(("UE_5.8", normal))
        self.registry.return_value = [discovery.EngineInstallation("StudioBuild", custom)]
        self.assertEqual(expected, discovery.find_installed_unreal_editor(["5.8"], association="studiobuild"))

    def test_missing_custom_build_does_not_fall_back_to_launcher_or_path(self) -> None:
        root = self.root / "launcher"
        executable = self.install(root)
        self.launcher(("UE_5.8", root))
        project = self.root / "project.uproject"
        project.write_text(json.dumps({"EngineAssociation": "StudioBuild"}))
        with patch("portable_pipe_tools.render_farm.unreal_runner.shutil.which", return_value=str(executable)):
            with self.assertRaisesRegex(FileNotFoundError, "StudioBuild"):
                resolve_unreal_editor_cmd({"uproject": str(project), "engine_version": "5.8"})

    def test_standard_install_location_still_works(self) -> None:
        expected = self.install(self.program_files / "Epic Games/UE_5.8")
        self.assertEqual(expected, discovery.find_installed_unreal_editor(["5.8"]))

    def test_path_engine_must_match_requested_version(self) -> None:
        executable = self.install(self.root / "path-engine", (5, 7))
        project = self.root / "project.uproject"
        project.write_text(json.dumps({"EngineAssociation": "5.8"}))
        with patch("portable_pipe_tools.render_farm.unreal_runner.shutil.which", return_value=str(executable)):
            with self.assertRaises(FileNotFoundError):
                resolve_unreal_editor_cmd({"uproject": str(project)})

    def test_matching_path_engine_is_accepted(self) -> None:
        executable = self.install(self.root / "path-engine")
        project = self.root / "project.uproject"
        project.write_text(json.dumps({"EngineAssociation": "5.8"}))
        with patch("portable_pipe_tools.render_farm.unreal_runner.shutil.which", return_value=str(executable)):
            self.assertEqual(executable, resolve_unreal_editor_cmd({"uproject": str(project)}))

    def test_unidentified_path_executable_is_not_accepted_for_known_version(self) -> None:
        executable = self.root / "UnrealEditor-Cmd.exe"
        executable.write_bytes(b"unidentified")
        self.assertFalse(discovery.path_engine_matches_versions(executable, ["5.8"]))

    def test_explicit_override_still_wins(self) -> None:
        expected = self.install(self.root / "explicit")
        self.assertEqual(expected.resolve(), resolve_unreal_editor_cmd({}, expected))


if __name__ == "__main__":
    unittest.main()
