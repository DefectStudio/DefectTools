import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.registered_sync import sync_registered_project
from portable_pipe_tools.render_farm.project_workspace import PreparationError, PreparationCancelled, ProjectWorkspace


class RegisteredSyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.seed = self.root / "seed"
        self.remote = self.root / "remote.git"
        self.checkout = self.root / "worker checkout"
        self.git(self.root, "init", "--bare", str(self.remote))
        self.git(self.root, "init", "-b", "main", str(self.seed))
        self.identity(self.seed)
        (self.seed / "Show").mkdir()
        (self.seed / "Show/Show.uproject").write_text("{}")
        (self.seed / "asset.txt").write_text("original")
        self.commit(self.seed, "Initial")
        self.git(self.seed, "remote", "add", "origin", str(self.remote))
        self.git(self.seed, "push", "-u", "origin", "main")
        self.git(self.root, "clone", "-b", "main", str(self.remote), str(self.checkout))
        self.identity(self.checkout)
        self.uproject = self.checkout / "Show/Show.uproject"

    def git(self, directory, *args):
        result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True,
                                env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file"), timeout=30)
        if result.returncode:
            self.fail(result.stderr)
        return result.stdout.strip()

    def identity(self, directory):
        self.git(directory, "config", "user.name", "Worker Test")
        self.git(directory, "config", "user.email", "worker@example.test")

    def commit(self, directory, message):
        self.git(directory, "add", ".")
        self.git(directory, "commit", "-m", message)
        return self.git(directory, "rev-parse", "HEAD")

    def sync(self, **kwargs):
        with patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "file"}):
            return sync_registered_project(self.uproject, self.root / "sync logs", progress=lambda _: None, **kwargs)

    def test_pulls_latest_current_branch_and_preserves_untracked_files(self):
        (self.seed / "asset.txt").write_text("updated")
        latest = self.commit(self.seed, "New asset")
        self.git(self.seed, "push")
        (self.checkout / "artist-note.txt").write_text("keep me")
        self.assertEqual(latest, self.sync())
        self.assertEqual("updated", (self.checkout / "asset.txt").read_text())
        self.assertEqual("keep me", (self.checkout / "artist-note.txt").read_text())
        self.assertEqual("main", self.git(self.checkout, "branch", "--show-current"))

    def test_tracked_edits_block_update_and_remain_intact(self):
        (self.checkout / "asset.txt").write_text("artist edits")
        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.sync()
        self.assertEqual("artist edits", (self.checkout / "asset.txt").read_text())

    def test_detached_checkout_is_not_switched(self):
        self.git(self.checkout, "checkout", "--detach")
        with self.assertRaisesRegex(PreparationError, "detached HEAD"):
            self.sync()
        self.assertEqual("", self.git(self.checkout, "branch", "--show-current"))

    def test_local_commits_do_not_render_as_latest_remote(self):
        (self.checkout / "asset.txt").write_text("unpublished")
        local = self.commit(self.checkout, "Unpublished")
        with self.assertRaisesRegex(PreparationError, "local commits"):
            self.sync()
        self.assertEqual(local, self.git(self.checkout, "rev-parse", "HEAD"))

    def test_diverged_history_fails_without_merging_or_resetting(self):
        (self.checkout / "local.txt").write_text("local")
        local = self.commit(self.checkout, "Local")
        (self.seed / "remote.txt").write_text("remote")
        self.commit(self.seed, "Remote")
        self.git(self.seed, "push")
        with self.assertRaises(PreparationError):
            self.sync()
        self.assertEqual(local, self.git(self.checkout, "rev-parse", "HEAD"))

    def test_cancelled_update_stops_before_commands(self):
        with self.assertRaises(PreparationCancelled):
            self.sync(cancelled=lambda: True)

    def test_lfs_failure_is_not_ignored(self):
        original = ProjectWorkspace.run
        def fail_lfs(instance, args, cwd, **kwargs):
            if args[:2] == ["lfs", "pull"]:
                raise PreparationError("LFS unavailable")
            return original(instance, args, cwd, **kwargs)
        with patch.object(ProjectWorkspace, "run", fail_lfs):
            with self.assertRaisesRegex(PreparationError, "LFS unavailable"):
                self.sync()

    def test_hydrates_lfs_and_initializes_pinned_submodule(self):
        self.git(self.seed, "lfs", "install", "--local")
        self.git(self.seed, "lfs", "track", "*.bin")
        payload = b"real binary asset\x00" * 100
        (self.seed / "texture.bin").write_bytes(payload)
        sub = self.root / "plugin-source"
        self.git(self.root, "init", "-b", "main", str(sub))
        self.identity(sub)
        self.git(sub, "lfs", "install", "--local")
        self.git(sub, "lfs", "track", "*.bin")
        (sub / "plugin.bin").write_bytes(payload)
        (sub / "plugin.txt").write_text("pinned plugin")
        pinned = self.commit(sub, "Plugin")
        self.git(self.seed, "submodule", "add", str(sub), "Show/Plugins/Common")
        latest = self.commit(self.seed, "LFS and plugin")
        self.git(self.seed, "push")
        self.assertEqual(latest, self.sync())
        self.assertEqual(payload, (self.checkout / "texture.bin").read_bytes())
        self.assertEqual(pinned, self.git(self.checkout / "Show/Plugins/Common", "rev-parse", "HEAD"))
        self.assertEqual(payload, (self.checkout / "Show/Plugins/Common/plugin.bin").read_bytes())
        (sub / "plugin.txt").write_text("updated plugin")
        next_pinned = self.commit(sub, "Plugin update")
        self.git(self.seed / "Show/Plugins/Common", "pull", "--ff-only")
        self.commit(self.seed, "Update plugin pointer")
        self.git(self.seed, "push")
        self.sync()
        self.assertEqual(next_pinned, self.git(self.checkout / "Show/Plugins/Common", "rev-parse", "HEAD"))
        (self.checkout / "Show/Plugins/Common/plugin.txt").write_text("artist plugin edit")
        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.sync()
