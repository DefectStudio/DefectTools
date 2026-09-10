from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.project_catalog import ProjectDefinition, load_catalog
from portable_pipe_tools.render_farm.project_workspace import (
    PreparationCancelled, PreparationError, ProjectWorkspace, project_lock,
)


class ProjectWorkspaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        metadata_environment = patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "metadata")})
        metadata_environment.start()
        self.addCleanup(metadata_environment.stop)
        self.source = self.root / "source"
        self.source.mkdir()
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Worker test")
        self.git("config", "user.email", "worker@example.invalid")
        (self.source / "Sample.uproject").write_text('{"EngineAssociation":"5.8"}')
        (self.source / "asset.txt").write_text("first")
        self.commit("initial")
        self.engine = self.root / "UnrealEditor-Cmd.exe"
        self.engine.write_bytes(b"test only")
        self.definition = ProjectDefinition.from_dict({"project_id": "sample", "revision": 1,
            "repository": str(self.source), "branch": "main", "uproject": "Sample.uproject", "lfs": False})
        self.workspace = ProjectWorkspace(self.root / "workspace", progress=lambda _: None, discovery_roots=())

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.source, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")

    def test_empty_workspace_clones_then_updates_to_latest_commit(self):
        (self.source / "earlier.txt").write_text("older history should not be cloned")
        self.commit("tip before clone")
        with self.workspace.acquire(self.definition, engine=self.engine) as first:
            self.assertEqual("first", (first.checkout / "asset.txt").read_text())
            first_commit = first.commit
            history = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=first.checkout,
                                     capture_output=True, text=True, check=True)
            self.assertEqual("1", history.stdout.strip())
        (self.source / "asset.txt").write_text("second")
        latest = self.commit("second")
        with self.workspace.acquire(self.definition, engine=self.engine) as second:
            self.assertEqual(latest, second.commit)
            self.assertNotEqual(first_commit, second.commit)
            self.assertEqual("second", (second.checkout / "asset.txt").read_text())

    def test_switching_projects_keeps_independent_workspaces(self):
        other = ProjectDefinition.from_dict({"project_id": "other", "repository": str(self.source),
            "branch": "main", "uproject": "Sample.uproject", "lfs": False})
        with self.workspace.acquire(self.definition, engine=self.engine) as first:
            first_root = first.checkout
        with self.workspace.acquire(other, engine=self.engine) as second:
            self.assertNotEqual(first_root, second.checkout)
            self.assertTrue((first_root / "Sample.uproject").is_file())

    def test_discovers_and_pulls_an_existing_clone_without_copying_it(self):
        existing = self.root / "artist-project"
        subprocess.run(["git", "clone", str(self.source), str(existing)], check=True, capture_output=True)
        (existing / "personal-notes.txt").write_text("keep untracked notes")
        (self.source / "asset.txt").write_text("latest")
        latest = self.commit("new source revision")
        self.workspace.discovery_roots = (self.root,)
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            self.assertEqual(existing.resolve(), prepared.checkout)
            self.assertEqual(latest, prepared.commit)
            self.assertEqual("latest", (existing / "asset.txt").read_text())
            self.assertEqual("keep untracked notes", (existing / "personal-notes.txt").read_text())
        self.assertFalse((self.workspace.root / "projects/sample").exists())
        self.assertFalse((existing / ".git/render-worker.json").exists())
        self.workspace.discovery_roots = ()
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            self.assertEqual(existing.resolve(), prepared.checkout)  # Remembered between jobs.

    def test_discovered_checkout_preserves_tracked_local_edits(self):
        existing = self.root / "artist-project"
        subprocess.run(["git", "clone", str(self.source), str(existing)], check=True, capture_output=True)
        (existing / "asset.txt").write_text("artist edit")
        self.workspace.discovery_roots = (self.root,)
        with self.assertRaisesRegex(PreparationError, "tracked local changes"):
            with self.workspace.acquire(self.definition, engine=self.engine):
                pass
        self.assertEqual("artist edit", (existing / "asset.txt").read_text())

    def test_editor_metadata_takes_priority_over_a_remembered_checkout_on_next_scan(self):
        previous = self.root / "previous"
        recent = self.root / "elsewhere/recent"
        recent.parent.mkdir()
        for checkout in (previous, recent):
            subprocess.run(["git", "clone", str(self.source), str(checkout)], check=True, capture_output=True)
        self.workspace.discovery_roots = (previous,)
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            self.assertEqual(previous.resolve(), prepared.checkout)
        settings = self.root / "metadata/UnrealEngine/5.8/Saved/Config/WindowsEditor/EditorSettings.ini"
        settings.parent.mkdir(parents=True)
        settings.write_text('[/Script/UnrealEd.EditorSettings]\n'
                            f'RecentlyOpenedProjectFiles=(ProjectName="{(recent / "Sample.uproject").as_posix()}",LastOpenTime=2026.09.10-10.00.00)\n')
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            self.assertEqual(recent.resolve(), prepared.checkout)

    def test_discovered_nested_checkout_is_locked_across_worker_workspaces(self):
        existing = self.root / "one/two/artist-project"
        existing.parent.mkdir(parents=True)
        subprocess.run(["git", "clone", str(self.source), str(existing)], check=True, capture_output=True)
        self.workspace.discovery_roots = (self.root,)
        other = ProjectWorkspace(self.root / "second-worker", discovery_roots=(existing,), progress=lambda _: None)
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            self.assertEqual(existing.resolve(), prepared.checkout)
            with self.assertRaisesRegex(PreparationError, "already using"):
                with other.acquire(self.definition, engine=self.engine):
                    pass

    def test_refuses_unmanaged_checkout_without_modifying_it(self):
        target = self.workspace.root / "projects/sample"
        target.mkdir(parents=True)
        marker = target / "artist-work.txt"
        marker.write_text("keep")
        with self.assertRaisesRegex(PreparationError, "unmanaged"):
            with self.workspace.acquire(self.definition, engine=self.engine):
                pass
        self.assertEqual("keep", marker.read_text())

    def test_dirty_managed_checkout_is_preserved(self):
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            file = prepared.checkout / "asset.txt"
            file.write_text("local change")
        with self.assertRaisesRegex(PreparationError, "local changes"):
            with self.workspace.acquire(self.definition, engine=self.engine):
                pass
        self.assertEqual("local change", file.read_text())

    def test_changed_repository_definition_is_rejected(self):
        with self.workspace.acquire(self.definition, engine=self.engine):
            pass
        changed = ProjectDefinition.from_dict({"project_id": "sample", "repository": str(self.root),
            "branch": "main", "uproject": "Sample.uproject", "lfs": False})
        with self.assertRaisesRegex(PreparationError, "does not match"):
            with self.workspace.acquire(changed, engine=self.engine):
                pass

    def test_cancellation_does_not_publish_a_project(self):
        workspace = ProjectWorkspace(self.root / "cancelled", cancelled=lambda: True)
        with self.assertRaises(PreparationCancelled):
            with workspace.acquire(self.definition, engine=self.engine):
                pass
        self.assertFalse((workspace.root / "projects/sample").exists())

    def test_project_lock_remains_held_during_render_scope(self):
        with self.workspace.acquire(self.definition, engine=self.engine):
            with self.assertRaisesRegex(PreparationError, "already using"):
                with project_lock(self.workspace.root / ".locks/sample.lock"):
                    pass
        with project_lock(self.workspace.root / ".locks/sample.lock"):
            pass

    def test_missing_engine_does_not_publish_half_prepared_project(self):
        with self.assertRaises(FileNotFoundError):
            with self.workspace.acquire(self.definition, engine=self.root / "absent.exe"):
                pass
        self.assertFalse((self.workspace.root / "projects/sample").exists())

    def test_failed_preparation_resumes_its_checkout_on_retry(self):
        with self.assertRaises(FileNotFoundError):
            with self.workspace.acquire(self.definition, engine=self.root / "absent.exe"):
                pass
        staging = list((self.workspace.root / ".staging").iterdir())
        self.assertEqual(1, len(staging))
        marker = staging[0] / ".git/retained-evidence"
        marker.write_text("same clone")
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            self.assertEqual("same clone", (prepared.checkout / ".git/retained-evidence").read_text())
        self.assertEqual([], list((self.workspace.root / ".staging").iterdir()))

    def test_catalog_rejects_traversal_credentials_and_duplicate_ids(self):
        base = {"project_id": "sample", "repository": str(self.source), "branch": "main", "uproject": "Sample.uproject"}
        for changed in [{"project_id": "../other"}, {"uproject": "../Sample.uproject"},
                        {"branch": "--upload-pack=bad"}, {"repository": "ext::bad"},
                        {"repository": "https://token@host.invalid/repo.git"}]:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                ProjectDefinition.from_dict(dict(base, **changed))
        catalog = self.root / "projects.json"
        catalog.write_text(json.dumps({"schema_version": 1, "projects": [base, base]}))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_catalog(catalog)

    def test_lfs_assets_are_fetched_without_a_machine_cache(self):
        self.git("lfs", "install", "--local")
        self.git("lfs", "track", "*.bin")
        payload = bytes(range(256)) * 64
        (self.source / "asset.bin").write_bytes(payload)
        self.commit("add LFS asset")
        definition = ProjectDefinition.from_dict({"project_id": "lfs-project", "repository": str(self.source),
            "branch": "main", "uproject": "Sample.uproject", "lfs": True})
        with self.workspace.acquire(definition, engine=self.engine) as prepared:
            self.assertEqual(payload, (prepared.checkout / "asset.bin").read_bytes())
        with self.workspace.acquire(definition, engine=self.engine) as prepared:
            self.assertEqual(payload, (prepared.checkout / "asset.bin").read_bytes())

    def test_runtime_installation_is_owned_and_does_not_dirty_checkout(self):
        from portable_pipe_tools.render_farm.project_render import install_runtime
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            install_runtime(prepared.checkout)
            self.assertTrue((prepared.checkout / "Plugins/RenderWorkerRuntime/RenderWorkerRuntime.uplugin").is_file())
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            install_runtime(prepared.checkout)

    def test_existing_unmanaged_runtime_plugin_is_not_overwritten(self):
        from portable_pipe_tools.render_farm.project_render import install_runtime
        with self.workspace.acquire(self.definition, engine=self.engine) as prepared:
            plugin = prepared.checkout / "Plugins/RenderWorkerRuntime"
            plugin.mkdir(parents=True)
            (plugin / "keep.txt").write_text("owned by artist")
            with self.assertRaisesRegex(RuntimeError, "unmanaged"):
                install_runtime(prepared.checkout)
            self.assertEqual("owned by artist", (plugin / "keep.txt").read_text())

    def test_runtime_is_installed_beside_a_nested_uproject(self):
        from portable_pipe_tools.render_farm.project_render import install_runtime
        nested = self.source / "Game"
        nested.mkdir()
        (self.source / "Sample.uproject").rename(nested / "Sample.uproject")
        self.commit("nested project")
        definition = ProjectDefinition.from_dict({"project_id": "nested", "repository": str(self.source),
            "branch": "main", "uproject": "Game/Sample.uproject", "lfs": False})
        with self.workspace.acquire(definition, engine=self.engine) as prepared:
            install_runtime(prepared.checkout, project_directory=prepared.uproject.parent)
            self.assertTrue((prepared.uproject.parent / "Plugins/RenderWorkerRuntime/RenderWorkerRuntime.uplugin").is_file())
        with self.workspace.acquire(definition, engine=self.engine):
            pass  # The injected nested plugin must not make the managed checkout dirty.


if __name__ == "__main__":
    unittest.main()
