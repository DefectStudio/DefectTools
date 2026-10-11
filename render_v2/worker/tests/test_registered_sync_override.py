"""Exercise explicit destructive sync using disposable local Git repositories."""

import base64
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.project_workspace import PreparationCancelled, PreparationError, ProjectWorkspace
from portable_pipe_tools.render_farm.registered_sync import sync_registered_project


class RegisteredSyncOverrideTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="worker-override-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.seed = self.root / "artist source"
        self.remote = self.root / "remote.git"
        self.checkout = self.root / "worker checkout"
        self.git(self.root, "init", "--bare", str(self.remote))
        self.git(self.root, "init", "-b", "main", str(self.seed))
        self.identity(self.seed)
        (self.seed / "Show").mkdir()
        (self.seed / "Show/Show.uproject").write_text("{}")
        (self.seed / ".gitignore").write_text("Show/Saved/\nShow/DerivedDataCache/\n")
        (self.seed / "asset.txt").write_text("original")
        (self.seed / "deleted.txt").write_text("restore this")
        (self.seed / "obsolete.txt").write_text("old published file")
        self.initial = self.commit(self.seed, "Initial published project")
        self.git(self.seed, "remote", "add", "origin", str(self.remote))
        self.git(self.seed, "push", "-u", "origin", "main")
        self.git(self.root, "clone", "-b", "main", str(self.remote), str(self.checkout))
        self.identity(self.checkout)
        self.uproject = self.checkout / "Show/Show.uproject"

    def git(self, directory, *args):
        result = subprocess.run(
            ["git", "-C", str(directory), *args], capture_output=True, text=True,
            env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file"), timeout=30,
        )
        if result.returncode:
            self.fail(f"Git {args[0]} failed in fixture: {result.stderr}")
        return result.stdout.strip()

    def identity(self, directory):
        self.git(directory, "config", "user.name", "Worker Override Test")
        self.git(directory, "config", "user.email", "worker-override@example.test")
        self.git(directory, "config", "core.autocrlf", "false")

    def commit(self, directory, message):
        self.git(directory, "add", ".")
        self.git(directory, "commit", "-m", message)
        return self.git(directory, "rev-parse", "HEAD")

    def publish(self, message):
        latest = self.commit(self.seed, message)
        self.git(self.seed, "push")
        return latest

    def sync(self, **kwargs):
        progress = kwargs.pop("progress", lambda _: None)
        with patch.dict(os.environ, {"GIT_ALLOW_PROTOCOL": "file"}):
            return sync_registered_project(
                self.uproject, self.root / "sync logs", progress=progress, **kwargs,
            )

    def assert_clean(self):
        self.assertEqual("", self.git(self.checkout, "status", "--porcelain", "--ignore-submodules=untracked"))

    def add_plugin(self, *, nested=False):
        source = self.root / "plugin source"
        self.git(self.root, "init", "-b", "main", str(source))
        self.identity(source)
        (source / "plugin.txt").write_text("managed plugin asset")
        self.commit(source, "Initial managed plugin")
        if nested:
            nested_source = self.root / "nested plugin source"
            self.git(self.root, "init", "-b", "main", str(nested_source))
            self.identity(nested_source)
            (nested_source / "nested.txt").write_text("managed nested plugin asset")
            self.commit(nested_source, "Initial managed nested plugin")
            self.git(source, "submodule", "add", str(nested_source), "Nested plugin")
            self.commit(source, "Register nested managed plugin")
        self.git(self.seed, "submodule", "add", str(source), "Show/Plugins/Common")
        self.publish("Register managed plugin")
        self.sync()
        checkout = self.checkout / "Show/Plugins/Common"
        self.identity(checkout)
        return source, checkout

    def directory_link(self, link, target):
        if os.name == "nt":
            # Junction creation needs no developer-mode/symlink privilege.
            # Encode literal paths so spaces and apostrophes cannot alter code.
            quote = lambda value: "'" + str(value).replace("'", "''") + "'"
            command = (f"New-Item -ItemType Junction -Path {quote(link)} "
                       f"-Value {quote(target)} -ErrorAction Stop | Out-Null")
            encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
            result = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                self.fail(f"Could not create isolated junction fixture: {result.stderr}")
        else:
            link.symlink_to(target, target_is_directory=True)
        self.addCleanup(self.remove_directory_link, link)

    @staticmethod
    def remove_directory_link(link):
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            # Removes the Windows junction itself without traversing its target.
            os.rmdir(link)

    def test_default_off_preserves_modified_deleted_staged_and_untracked_files(self):
        (self.checkout / "asset.txt").write_text("artist's local edit")
        (self.checkout / "deleted.txt").unlink()
        (self.checkout / "staged.txt").write_text("unpublished staged work")
        self.git(self.checkout, "add", "staged.txt")
        (self.checkout / "artist-note.txt").write_text("local note")
        staged_before = self.git(self.checkout, "diff", "--cached", "--raw")

        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.sync()

        self.assertEqual(self.initial, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual("artist's local edit", (self.checkout / "asset.txt").read_text())
        self.assertFalse((self.checkout / "deleted.txt").exists())
        self.assertEqual(staged_before, self.git(self.checkout, "diff", "--cached", "--raw"))
        self.assertEqual("local note", (self.checkout / "artist-note.txt").read_text())

    def test_override_gets_latest_and_discards_all_local_checkout_differences(self):
        (self.seed / "asset.txt").write_text("latest published asset")
        (self.seed / "obsolete.txt").unlink()
        (self.seed / "new asset.txt").write_text("new published asset")
        latest = self.publish("Publish newest timeline changes")
        (self.checkout / "asset.txt").write_text("local asset edit")
        (self.checkout / "deleted.txt").unlink()
        (self.checkout / "staged.txt").write_text("local staged addition")
        self.git(self.checkout, "add", "staged.txt")
        (self.checkout / "new asset.txt").write_text("untracked checkout blocker")
        (self.checkout / "untracked folder").mkdir()
        (self.checkout / "untracked folder/note.txt").write_text("local untracked work")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertEqual(latest, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual("main", self.git(self.checkout, "branch", "--show-current"))
        self.assertEqual("latest published asset", (self.checkout / "asset.txt").read_text())
        self.assertEqual("restore this", (self.checkout / "deleted.txt").read_text())
        self.assertEqual("new published asset", (self.checkout / "new asset.txt").read_text())
        self.assertFalse((self.checkout / "obsolete.txt").exists())
        self.assertFalse((self.checkout / "staged.txt").exists())
        self.assertFalse((self.checkout / "untracked folder").exists())
        self.assert_clean()

    def test_override_preserves_ignored_render_outputs_and_caches(self):
        outputs = self.checkout / "Show/Saved/Renders/shot.exr"
        cache = self.checkout / "Show/DerivedDataCache/shader.cache"
        for path in (outputs, cache):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"keep existing production data\x00")
        (self.checkout / "asset.txt").write_text("local difference")
        (self.checkout / "untracked.txt").write_text("discard opted-in local file")

        self.sync(override_local_changes=True)

        self.assertEqual(b"keep existing production data\x00", outputs.read_bytes())
        self.assertEqual(b"keep existing production data\x00", cache.read_bytes())
        self.assertFalse((self.checkout / "untracked.txt").exists())
        self.assert_clean()

    def test_override_discards_divergent_local_commits_for_fetched_upstream(self):
        (self.checkout / "local-only.txt").write_text("unpublished local commit")
        local = self.commit(self.checkout, "Local unpublished history")
        (self.seed / "asset.txt").write_text("new upstream history")
        latest = self.publish("Remote history diverges")
        self.assertNotEqual(local, latest)

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertFalse((self.checkout / "local-only.txt").exists())
        self.assertEqual("new upstream history", (self.checkout / "asset.txt").read_text())
        self.assert_clean()

    def test_override_follows_force_rewritten_upstream_instead_of_stale_tracking_ref(self):
        (self.seed / "superseded.txt").write_text("published history that will be replaced")
        prior = self.publish("Original published history")
        self.sync()
        self.git(self.seed, "reset", "--hard", self.initial)
        (self.seed / "asset.txt").write_text("rewritten published timeline")
        rewritten = self.commit(self.seed, "Replacement published history")
        self.git(self.seed, "push", "--force", "origin", "main")
        self.assertEqual(prior, self.git(self.checkout, "rev-parse", "origin/main"))
        (self.checkout / "asset.txt").write_text("local asset difference")

        self.assertEqual(rewritten, self.sync(override_local_changes=True))

        self.assertEqual(rewritten, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(rewritten, self.git(self.checkout, "rev-parse", "origin/main"))
        self.assertEqual("rewritten published timeline", (self.checkout / "asset.txt").read_text())
        self.assertFalse((self.checkout / "superseded.txt").exists())
        self.assert_clean()

    def test_override_keeps_current_registered_branch_instead_of_switching_to_main(self):
        self.git(self.seed, "checkout", "-b", "render-branch")
        (self.seed / "asset.txt").write_text("render branch asset")
        self.commit(self.seed, "Start render branch")
        self.git(self.seed, "push", "-u", "origin", "render-branch")
        self.git(self.checkout, "fetch", "origin")
        self.git(self.checkout, "checkout", "-b", "render-branch", "--track", "origin/render-branch")
        (self.seed / "asset.txt").write_text("latest render branch asset")
        latest = self.publish("Advance render branch")
        (self.checkout / "asset.txt").write_text("local render branch difference")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertEqual("render-branch", self.git(self.checkout, "branch", "--show-current"))
        self.assertEqual("latest render branch asset", (self.checkout / "asset.txt").read_text())
        self.assert_clean()

    def test_override_missing_upstream_preserves_local_changes(self):
        self.git(self.checkout, "branch", "--unset-upstream")
        (self.checkout / "asset.txt").write_text("must survive missing upstream")
        (self.checkout / "untracked.txt").write_text("must also survive")

        with self.assertRaises(PreparationError):
            self.sync(override_local_changes=True)

        self.assertEqual(self.initial, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual("must survive missing upstream", (self.checkout / "asset.txt").read_text())
        self.assertEqual("must also survive", (self.checkout / "untracked.txt").read_text())

    def test_override_fetch_failure_preserves_head_index_and_files(self):
        (self.checkout / "asset.txt").write_text("preserve failed-fetch edits")
        self.git(self.checkout, "add", "asset.txt")
        (self.checkout / "untracked.txt").write_text("preserve failed-fetch untracked file")
        before = self.git(self.checkout, "diff", "--cached", "--raw")
        self.git(self.checkout, "remote", "set-url", "origin", str(self.root / "missing remote.git"))

        with self.assertRaises(PreparationError):
            self.sync(override_local_changes=True)

        self.assertEqual(self.initial, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(before, self.git(self.checkout, "diff", "--cached", "--raw"))
        self.assertEqual("preserve failed-fetch edits", (self.checkout / "asset.txt").read_text())
        self.assertEqual("preserve failed-fetch untracked file", (self.checkout / "untracked.txt").read_text())

    def test_override_remote_missing_registered_project_preserves_local_files(self):
        (self.seed / "Show/Show.uproject").unlink()
        self.publish("Remove registered project from upstream")
        (self.checkout / "asset.txt").write_text("keep invalid-target local edits")
        (self.checkout / "untracked.txt").write_text("keep invalid-target untracked file")

        with self.assertRaises(PreparationError):
            self.sync(override_local_changes=True)

        self.assertEqual(self.initial, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertTrue(self.uproject.is_file())
        self.assertEqual("keep invalid-target local edits", (self.checkout / "asset.txt").read_text())
        self.assertEqual("keep invalid-target untracked file", (self.checkout / "untracked.txt").read_text())

    def test_override_detached_checkout_is_not_switched_or_cleaned(self):
        self.git(self.checkout, "checkout", "--detach")
        (self.checkout / "asset.txt").write_text("keep detached edits")
        (self.checkout / "untracked.txt").write_text("keep detached untracked file")

        with self.assertRaisesRegex(PreparationError, "detached HEAD"):
            self.sync(override_local_changes=True)

        self.assertEqual("", self.git(self.checkout, "branch", "--show-current"))
        self.assertEqual("keep detached edits", (self.checkout / "asset.txt").read_text())
        self.assertEqual("keep detached untracked file", (self.checkout / "untracked.txt").read_text())

    def test_override_cancelled_before_preparation_does_not_discard_files(self):
        (self.checkout / "asset.txt").write_text("keep cancelled edits")
        with self.assertRaises(PreparationCancelled):
            self.sync(override_local_changes=True, cancelled=lambda: True)
        self.assertEqual("keep cancelled edits", (self.checkout / "asset.txt").read_text())

    def test_override_requires_an_explicit_boolean_before_touching_checkout(self):
        (self.checkout / "asset.txt").write_text("keep malformed-option local edits")
        for value in ("False", "True", 1, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.sync(override_local_changes=value)
                self.assertEqual("keep malformed-option local edits", (self.checkout / "asset.txt").read_text())

    def test_override_hydrates_published_lfs_binary_after_discarding_local_changes(self):
        self.git(self.seed, "lfs", "install", "--local")
        self.git(self.seed, "lfs", "track", "*.bin")
        payload = b"published linear render asset\x00" * 64
        (self.seed / "texture.bin").write_bytes(payload)
        latest = self.publish("Publish LFS asset")
        (self.checkout / "texture.bin").write_bytes(b"untracked local binary blocker")
        (self.checkout / "asset.txt").write_text("unwanted local difference")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertEqual(payload, (self.checkout / "texture.bin").read_bytes())
        self.assert_clean()

    def test_override_lfs_failure_still_refuses_to_render(self):
        (self.checkout / "asset.txt").write_text("opted-in local difference")
        original = ProjectWorkspace.run

        def fail_lfs(instance, args, cwd, **kwargs):
            if args[:2] == ["lfs", "pull"]:
                raise PreparationError("Fixture LFS download failed")
            return original(instance, args, cwd, **kwargs)

        with patch.object(ProjectWorkspace, "run", fail_lfs):
            with self.assertRaisesRegex(PreparationError, "Fixture LFS download failed"):
                self.sync(override_local_changes=True)

    def test_override_stat_only_modified_status_uses_actual_content_validation(self):
        original = ProjectWorkspace.run
        hydrated = False

        def status_with_stale_metadata(instance, args, cwd, **kwargs):
            nonlocal hydrated
            result = original(instance, args, cwd, **kwargs)
            if args[:2] == ["lfs", "pull"]:
                hydrated = True
            if hydrated and args[0] == "status" and kwargs.get("capture"):
                return " M asset.txt"
            return result

        with patch.object(ProjectWorkspace, "run", status_with_stale_metadata):
            self.assertEqual(self.initial, self.sync(override_local_changes=True))

        self.assertEqual("original", (self.checkout / "asset.txt").read_text())
        self.assert_clean()

    def test_override_actual_edit_during_hydration_still_refuses_to_render(self):
        original = ProjectWorkspace.run

        def edit_during_lfs(instance, args, cwd, **kwargs):
            result = original(instance, args, cwd, **kwargs)
            if args[:2] == ["lfs", "pull"]:
                (self.checkout / "asset.txt").write_text("real concurrent artist edit")
            return result

        with patch.object(ProjectWorkspace, "run", edit_during_lfs):
            with self.assertRaises(PreparationError):
                self.sync(override_local_changes=True)

        self.assertEqual("real concurrent artist edit", (self.checkout / "asset.txt").read_text())

    def test_override_resets_dirty_recursive_submodules_to_new_project_pins(self):
        nested_source = self.root / "nested plugin source"
        self.git(self.root, "init", "-b", "main", str(nested_source))
        self.identity(nested_source)
        (nested_source / "nested.txt").write_text("old nested asset")
        self.commit(nested_source, "Initial nested plugin")
        source = self.root / "plugin source"
        self.git(self.root, "init", "-b", "main", str(source))
        self.identity(source)
        (source / "plugin.txt").write_text("old plugin asset")
        (source / ".gitignore").write_text("Saved/\n")
        self.commit(source, "Initial plugin")
        self.git(source, "submodule", "add", str(nested_source), "Nested plugin")
        self.commit(source, "Add nested plugin")
        self.git(self.seed, "submodule", "add", str(source), "Show/Plugins/Common")
        self.publish("Register plugin")
        self.sync()
        plugin = self.checkout / "Show/Plugins/Common"
        nested = plugin / "Nested plugin"
        self.identity(plugin)
        self.identity(nested)
        (plugin / "plugin.txt").write_text("unpublished local plugin")
        self.commit(plugin, "Unpublished plugin changes")
        (nested / "nested.txt").write_text("staged local nested changes")
        self.git(nested, "add", "nested.txt")
        (nested / "untracked.txt").write_text("discard nested untracked file")
        preserved_cache = plugin / "Saved/local.cache"
        preserved_cache.parent.mkdir()
        preserved_cache.write_text("preserve ignored child cache")

        (nested_source / "nested.txt").write_text("new published nested asset")
        new_nested = self.commit(nested_source, "Advance nested plugin")
        self.git(source / "Nested plugin", "fetch", "origin")
        self.git(source / "Nested plugin", "checkout", "--detach", new_nested)
        (source / "plugin.txt").write_text("new published plugin asset")
        new_plugin = self.commit(source, "Adopt nested pin and publish plugin")
        self.git(self.seed / "Show/Plugins/Common", "fetch", "--recurse-submodules=no", "origin")
        self.git(self.seed / "Show/Plugins/Common", "checkout", "--detach", new_plugin)
        latest = self.publish("Adopt newest recursive plugin pins")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertEqual(new_plugin, self.git(plugin, "rev-parse", "HEAD"))
        self.assertEqual(new_nested, self.git(nested, "rev-parse", "HEAD"))
        self.assertEqual("new published plugin asset", (plugin / "plugin.txt").read_text())
        self.assertEqual("new published nested asset", (nested / "nested.txt").read_text())
        self.assertFalse((nested / "untracked.txt").exists())
        self.assertEqual("preserve ignored child cache", preserved_cache.read_text())
        self.assert_clean()

    def test_override_removes_previously_managed_submodule_deleted_upstream(self):
        _, plugin = self.add_plugin()
        (plugin / "plugin.txt").write_text("discard opted-in old plugin edit")
        (plugin / "local-note.txt").write_text("discard old plugin untracked work")
        self.git(self.seed, "rm", "-f", "Show/Plugins/Common")
        latest = self.publish("Remove managed plugin from project")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertFalse((plugin / "plugin.txt").exists())
        self.assertFalse((plugin / ".git").exists())
        self.assert_clean()

    def test_override_replaces_managed_submodule_with_ordinary_upstream_files(self):
        _, plugin = self.add_plugin()
        (plugin / "plugin.txt").write_text("discard old managed plugin changes")
        self.git(self.seed, "rm", "-f", "Show/Plugins/Common")
        replacement = self.seed / "Show/Plugins/Common"
        replacement.mkdir()
        (replacement / "ordinary.txt").write_text("published regular project files")
        latest = self.publish("Replace managed plugin with regular files")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertEqual("published regular project files", (plugin / "ordinary.txt").read_text())
        self.assertFalse((plugin / "plugin.txt").exists())
        self.assertFalse((plugin / ".git").exists())
        self.assert_clean()

    def test_override_replaces_managed_submodule_with_an_ordinary_upstream_file(self):
        _, plugin = self.add_plugin()
        (plugin / "plugin.txt").write_text("discard opted-in obsolete plugin edit")
        self.git(self.seed, "rm", "-f", "Show/Plugins/Common")
        (self.seed / "Show/Plugins/Common").write_text("published ordinary replacement file")
        latest = self.publish("Replace plugin directory with an ordinary file")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertTrue(plugin.is_file())
        self.assertEqual("published ordinary replacement file", plugin.read_text())
        self.assert_clean()

    def test_override_removes_obsolete_nested_managed_submodule(self):
        source, plugin = self.add_plugin(nested=True)
        nested = plugin / "Nested plugin"
        (nested / "nested.txt").write_text("discard opted-in nested plugin changes")
        (nested / "local-note.txt").write_text("discard obsolete nested untracked work")
        self.git(source, "rm", "-f", "Nested plugin")
        new_plugin = self.commit(source, "Remove nested managed plugin")
        self.git(self.seed / "Show/Plugins/Common", "fetch", "--recurse-submodules=no", "origin")
        self.git(self.seed / "Show/Plugins/Common", "checkout", "--detach", new_plugin)
        latest = self.publish("Adopt parent plugin with nested plugin removed")

        self.assertEqual(latest, self.sync(override_local_changes=True))

        self.assertEqual(new_plugin, self.git(plugin, "rev-parse", "HEAD"))
        self.assertFalse((nested / "nested.txt").exists())
        self.assertFalse((nested / ".git").exists())
        self.assert_clean()

    def test_override_rejects_staged_gitlink_and_matching_child_changed_during_hydration(self):
        source, plugin = self.add_plugin()
        pinned = self.git(plugin, "rev-parse", "HEAD")
        (source / "plugin.txt").write_text("different published child asset")
        alternate = self.commit(source, "Alternate published child version")
        self.git(plugin, "fetch", "origin")
        original = ProjectWorkspace.run
        changed = False

        def stage_different_pin_during_lfs(instance, args, cwd, **kwargs):
            nonlocal changed
            result = original(instance, args, cwd, **kwargs)
            if (not changed and args[:2] == ["lfs", "pull"]
                    and Path(cwd).resolve() == self.checkout.resolve()):
                changed = True
                self.git(plugin, "checkout", "--detach", alternate)
                self.git(self.checkout, "add", "Show/Plugins/Common")
            return result

        with patch.object(ProjectWorkspace, "run", stage_different_pin_during_lfs):
            with self.assertRaises(PreparationError):
                self.sync(override_local_changes=True)

        self.assertTrue(changed)
        self.assertNotEqual(pinned, alternate)
        self.assertEqual(alternate, self.git(plugin, "rev-parse", "HEAD"))
        self.assertIn(alternate, self.git(self.checkout, "ls-files", "--stage", "Show/Plugins/Common"))

    def test_override_fails_for_unknown_embedded_git_repository_without_deleting_it(self):
        embedded = self.checkout / "Show/Plugins/LocalExperiment"
        embedded.parent.mkdir(parents=True)
        self.git(self.checkout, "init", "-b", "main", str(embedded))
        self.identity(embedded)
        (embedded / "LocalExperiment.uplugin").write_text('{"FileVersion": 3}')
        (embedded / "asset.txt").write_text("independent plugin asset")
        embedded_head = self.commit(embedded, "Independent unpublished embedded plugin")
        (embedded / "asset.txt").write_text("protect independent local plugin edit")
        (embedded / "local-note.txt").write_text("protect independent untracked plugin file")
        (self.checkout / "asset.txt").write_text("opted-in parent difference")

        with self.assertRaisesRegex(PreparationError, "untracked|unmanaged|embedded|repository"):
            self.sync(override_local_changes=True)

        self.assertTrue((embedded / ".git").is_dir())
        self.assertEqual(embedded_head, self.git(embedded, "rev-parse", "HEAD"))
        self.assertEqual("protect independent local plugin edit", (embedded / "asset.txt").read_text())
        self.assertEqual("protect independent untracked plugin file", (embedded / "local-note.txt").read_text())

    def test_override_rejects_child_junction_outside_project_before_discarding_any_files(self):
        _, plugin = self.add_plugin()
        before = self.git(self.checkout, "rev-parse", "HEAD")
        outside = self.root / "outside checkout"
        self.git(self.root, "init", "-b", "main", str(outside))
        self.identity(outside)
        (outside / "outside.txt").write_text("published outside file")
        outside_head = self.commit(outside, "Independent outside repository")
        (outside / "outside.txt").write_text("protect outside local edits")
        (outside / "untracked.txt").write_text("protect outside untracked file")
        # Only remove the disposable fixture checkout, verified inside its root.
        self.assertTrue(plugin.resolve().is_relative_to(self.checkout.resolve()))
        shutil.rmtree(plugin)
        self.directory_link(plugin, outside)
        (self.checkout / "asset.txt").write_text("protect parent local edits")
        (self.checkout / "untracked.txt").write_text("protect parent untracked file")

        with self.assertRaisesRegex(PreparationError, "outside"):
            self.sync(override_local_changes=True)

        self.assertEqual(before, self.git(self.checkout, "rev-parse", "HEAD"))
        self.assertEqual(outside_head, self.git(outside, "rev-parse", "HEAD"))
        self.assertEqual("protect parent local edits", (self.checkout / "asset.txt").read_text())
        self.assertEqual("protect parent untracked file", (self.checkout / "untracked.txt").read_text())
        self.assertEqual("protect outside local edits", (outside / "outside.txt").read_text())
        self.assertEqual("protect outside untracked file", (outside / "untracked.txt").read_text())


if __name__ == "__main__":
    unittest.main()
