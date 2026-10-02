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

    def add_plugin(self, *, nested=False):
        source = self.root / "plugin source"
        self.git(self.root, "init", "-b", "main", str(source))
        self.identity(source)
        (source / "plugin.txt").write_text("pinned plugin")
        self.commit(source, "Plugin")
        nested_source = None
        if nested:
            nested_source = self.root / "nested source"
            self.git(self.root, "init", "-b", "main", str(nested_source))
            self.identity(nested_source)
            (nested_source / "nested.txt").write_text("pinned nested plugin")
            self.commit(nested_source, "Nested plugin")
            self.git(source, "submodule", "add", str(nested_source), "Nested plugin")
            self.commit(source, "Add nested plugin")
        self.git(self.seed, "submodule", "add", str(source), "Show/Plugins/Common")
        self.commit(self.seed, "Add plugin")
        self.git(self.seed, "push")
        self.sync()
        checkout = self.checkout / "Show/Plugins/Common"
        self.identity(checkout)
        return source, checkout, nested_source

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

    def test_clean_published_submodule_drift_returns_to_project_pin(self):
        source, checkout, _ = self.add_plugin()
        pinned = self.git(checkout, "rev-parse", "HEAD")
        (source / "plugin.txt").write_text("new published plugin")
        published = self.commit(source, "Published plugin update")
        self.git(checkout, "fetch", "origin")
        self.git(checkout, "checkout", "--detach", published)
        (checkout / "artist-note.txt").write_text("keep me")
        project_head = self.git(self.checkout, "rev-parse", "HEAD")
        self.assertEqual(project_head, self.sync())
        self.assertEqual(pinned, self.git(checkout, "rev-parse", "HEAD"))
        self.assertEqual("pinned plugin", (checkout / "plugin.txt").read_text())
        self.assertEqual("keep me", (checkout / "artist-note.txt").read_text())
        self.assertEqual("", self.git(self.checkout, "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=untracked"))

    def test_clean_submodule_behind_new_parent_pin_is_updated(self):
        source, checkout, _ = self.add_plugin()
        old_pin = self.git(checkout, "rev-parse", "HEAD")
        (source / "plugin.txt").write_text("new published plugin")
        published = self.commit(source, "Published plugin update")
        seed_plugin = self.seed / "Show/Plugins/Common"
        self.git(seed_plugin, "fetch", "origin")
        self.git(seed_plugin, "checkout", "--detach", published)
        updated_parent = self.commit(self.seed, "Adopt new plugin pin")
        self.git(self.seed, "push")
        self.assertEqual(old_pin, self.git(checkout, "rev-parse", "HEAD"))
        self.assertEqual(updated_parent, self.sync())
        self.assertEqual(published, self.git(checkout, "rev-parse", "HEAD"))
        self.assertEqual("new published plugin", (checkout / "plugin.txt").read_text())

    def test_clean_published_nested_submodule_drift_returns_to_pin(self):
        _, checkout, source = self.add_plugin(nested=True)
        nested = checkout / "Nested plugin"
        pinned = self.git(nested, "rev-parse", "HEAD")
        (source / "nested.txt").write_text("new published nested plugin")
        published = self.commit(source, "Published nested update")
        self.git(nested, "fetch", "origin")
        self.git(nested, "checkout", "--detach", published)
        (nested / "artist-note.txt").write_text("keep me")
        self.sync()
        self.assertEqual(pinned, self.git(nested, "rev-parse", "HEAD"))
        self.assertEqual("pinned nested plugin", (nested / "nested.txt").read_text())
        self.assertEqual("keep me", (nested / "artist-note.txt").read_text())

    def test_staged_parent_gitlink_is_preserved(self):
        source, checkout, _ = self.add_plugin()
        (source / "plugin.txt").write_text("new published plugin")
        published = self.commit(source, "Published plugin update")
        self.git(checkout, "fetch", "origin")
        self.git(checkout, "checkout", "--detach", published)
        self.git(self.checkout, "add", "Show/Plugins/Common")
        staged = self.git(self.checkout, "diff", "--cached", "--raw")
        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.sync()
        self.assertEqual(staged, self.git(self.checkout, "diff", "--cached", "--raw"))
        self.assertEqual(published, self.git(checkout, "rev-parse", "HEAD"))

    def test_staged_submodule_edit_is_preserved(self):
        _, checkout, _ = self.add_plugin()
        (checkout / "plugin.txt").write_text("artist plugin edit")
        self.git(checkout, "add", "plugin.txt")
        staged = self.git(checkout, "diff", "--cached", "--raw")
        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.sync()
        self.assertEqual("artist plugin edit", (checkout / "plugin.txt").read_text())
        self.assertEqual(staged, self.git(checkout, "diff", "--cached", "--raw"))

    def test_unpublished_detached_submodule_commit_is_preserved(self):
        _, checkout, _ = self.add_plugin()
        self.git(checkout, "checkout", "--detach")
        (checkout / "plugin.txt").write_text("unpublished artist plugin")
        unpublished = self.commit(checkout, "Unpublished plugin edit")
        with self.assertRaisesRegex(PreparationError, "local unpublished commits"):
            self.sync()
        self.assertEqual(unpublished, self.git(checkout, "rev-parse", "HEAD"))
        self.assertEqual("unpublished artist plugin", (checkout / "plugin.txt").read_text())

    def test_parent_pull_does_not_displace_previously_pinned_unpublished_commit(self):
        source, checkout, _ = self.add_plugin()
        (checkout / "plugin.txt").write_text("unpublished artist plugin")
        unpublished = self.commit(checkout, "Unpublished plugin edit")
        seed_plugin = self.seed / "Show/Plugins/Common"
        self.git(seed_plugin, "fetch", str(checkout), unpublished)
        self.git(seed_plugin, "checkout", "--detach", unpublished)
        self.commit(self.seed, "Pin unpublished plugin")
        self.git(self.seed, "push")
        self.git(self.checkout, "pull", "--ff-only", "--recurse-submodules=no")
        (source / "plugin.txt").write_text("new published plugin")
        published = self.commit(source, "Published plugin update")
        self.git(seed_plugin, "fetch", "origin")
        self.git(seed_plugin, "checkout", "--detach", published)
        updated_parent = self.commit(self.seed, "Pin published plugin")
        self.git(self.seed, "push")
        with self.assertRaisesRegex(PreparationError, "local unpublished commits"):
            self.sync()
        self.assertEqual(updated_parent, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(unpublished, self.git(checkout, "rev-parse", "HEAD"))
        self.assertEqual("unpublished artist plugin", (checkout / "plugin.txt").read_text())

    def test_nested_submodule_edits_are_preserved(self):
        _, checkout, _ = self.add_plugin(nested=True)
        nested = checkout / "Nested plugin"
        (nested / "nested.txt").write_text("nested artist edit")
        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.sync()
        self.assertEqual("nested artist edit", (nested / "nested.txt").read_text())

    def test_nested_unpublished_detached_commit_is_preserved(self):
        _, checkout, _ = self.add_plugin(nested=True)
        nested = checkout / "Nested plugin"
        self.identity(nested)
        self.git(nested, "checkout", "--detach")
        (nested / "nested.txt").write_text("unpublished nested artist plugin")
        unpublished = self.commit(nested, "Unpublished nested plugin edit")
        with self.assertRaisesRegex(PreparationError, "local unpublished commits"):
            self.sync()
        self.assertEqual(unpublished, self.git(nested, "rev-parse", "HEAD"))

    def test_moving_parent_preserves_nested_commit_at_its_old_pin(self):
        source, checkout, nested_source = self.add_plugin(nested=True)
        nested = checkout / "Nested plugin"
        self.identity(nested)
        (nested / "nested.txt").write_text("unpublished nested artist plugin")
        unpublished = self.commit(nested, "Unpublished nested plugin edit")
        old_plugin = self.commit(checkout, "Pin unpublished nested plugin")
        self.git(source, "fetch", "--recurse-submodules=no", str(checkout), old_plugin)
        self.git(source, "-c", "submodule.recurse=false", "merge", "--ff-only", old_plugin)
        self.git(checkout, "fetch", "--recurse-submodules=no", "origin")
        seed_plugin = self.seed / "Show/Plugins/Common"
        self.git(seed_plugin, "fetch", "--recurse-submodules=no", "origin")
        self.git(seed_plugin, "checkout", "--detach", old_plugin)
        self.commit(self.seed, "Pin old plugin")
        self.git(self.seed, "push")
        self.git(self.checkout, "pull", "--ff-only", "--recurse-submodules=no")
        (nested_source / "nested.txt").write_text("new published nested plugin")
        new_nested = self.commit(nested_source, "Published nested plugin update")
        source_nested = source / "Nested plugin"
        self.git(source_nested, "fetch", "origin")
        self.git(source_nested, "checkout", "--detach", new_nested)
        new_plugin = self.commit(source, "Pin new nested plugin")
        self.git(seed_plugin, "fetch", "--recurse-submodules=no", "origin")
        self.git(seed_plugin, "checkout", "--detach", new_plugin)
        new_parent = self.commit(self.seed, "Pin new plugin")
        self.git(self.seed, "push")
        with self.assertRaisesRegex(PreparationError, "local unpublished commits"):
            self.sync()
        self.assertEqual(new_parent, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(old_plugin, self.git(checkout, "rev-parse", "HEAD"))
        self.assertEqual(unpublished, self.git(nested, "rev-parse", "HEAD"))

    def test_aligned_nested_pins_need_no_remote_containment_proof(self):
        _, checkout, _ = self.add_plugin(nested=True)
        nested = checkout / "Nested plugin"
        self.git(checkout, "update-ref", "-d", "refs/remotes/origin/main")
        self.git(nested, "update-ref", "-d", "refs/remotes/origin/main")
        pinned = self.git(checkout, "rev-parse", "HEAD")
        nested_pinned = self.git(nested, "rev-parse", "HEAD")
        self.sync()
        self.assertEqual(pinned, self.git(checkout, "rev-parse", "HEAD"))
        self.assertEqual(nested_pinned, self.git(nested, "rev-parse", "HEAD"))

    def test_staged_nested_gitlink_is_preserved(self):
        _, checkout, source = self.add_plugin(nested=True)
        nested = checkout / "Nested plugin"
        (source / "nested.txt").write_text("new nested plugin")
        published = self.commit(source, "Published nested update")
        self.git(nested, "fetch", "origin")
        self.git(nested, "checkout", "--detach", published)
        self.git(checkout, "add", "Nested plugin")
        staged = self.git(checkout, "diff", "--cached", "--raw")
        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.sync()
        self.assertEqual(staged, self.git(checkout, "diff", "--cached", "--raw"))
        self.assertEqual(published, self.git(nested, "rev-parse", "HEAD"))

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
