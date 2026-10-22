"""Regression coverage for reusing assets after an LFS cache was pruned."""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm.lfs_hydration import (
    check_disk_space, hydrate_registered_assets, registered_git_config,
)
from portable_pipe_tools.render_farm.lfs_pointer_filter import pointer_for_chunks, process_filter
from portable_pipe_tools.render_farm.project_workspace import InsufficientDiskSpace, PreparationError


class LfsHydrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="worker-lfs-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.media = self.root / ".git/lfs/objects"
        self.payload = b"Already downloaded project asset\x00" * 100
        self.oid = hashlib.sha256(self.payload).hexdigest()
        self.items = []
        self.calls = []

    def asset(self, name, *, content=None, cached=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.payload if content is None else content)
        self.items.append({"name": name, "oid": self.oid, "size": len(self.payload)})
        if cached:
            self.cache_asset()
        return path

    def cache_asset(self):
        path = self.media / self.oid[:2] / self.oid[2:4] / self.oid
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.payload)
        return path

    def git_run(self, args, cwd=None, capture=False):
        self.calls.append(args)
        if args[:3] == ["lfs", "ls-files", "--json"]:
            return json.dumps({"files": self.items})
        if args == ["lfs", "env"]:
            return f"LocalMediaDir={self.media}"
        if args[:2] == ["lfs", "fetch"]:
            self.cache_asset()
            return ""
        self.fail(f"Unexpected Git command: {args}")

    def hydrate(self, **kwargs):
        return hydrate_registered_assets(self.git_run, [self.root], self.root / "logs",
                                         progress=lambda _: None, check_cancelled=lambda: None, **kwargs)

    def test_verified_worktree_does_not_download_or_recreate_cache(self):
        path = self.asset("Content/already here.uasset")
        self.hydrate()
        self.assertEqual(self.payload, path.read_bytes())
        self.assertFalse(self.media.exists())
        self.assertFalse(any(args[:2] == ["lfs", "fetch"] for args in self.calls))

    def test_same_size_modified_asset_is_preserved_without_downloading(self):
        path = self.asset("Content/changed.uasset", content=b"x" * len(self.payload))
        with self.assertRaisesRegex(PreparationError, "local changes"):
            self.hydrate()
        self.assertEqual(b"x" * len(self.payload), path.read_bytes())
        self.assertFalse(self.media.exists())

    def test_placeholder_reuses_verified_sibling_without_cache(self):
        self.asset("Content/ready.uasset")
        restored = self.asset("Content/copy.uasset", content=pointer_for_chunks([self.payload]))
        self.hydrate()
        self.assertEqual(self.payload, restored.read_bytes())
        self.assertFalse(self.media.exists())

    def test_placeholder_reuses_cache_without_download_and_without_hardlinks(self):
        path = self.asset("Content/placeholder.uasset", content=pointer_for_chunks([self.payload]), cached=True)
        self.hydrate()
        path.write_bytes(b"edited working file")
        cached = self.media / self.oid[:2] / self.oid[2:4] / self.oid
        self.assertEqual(self.payload, cached.read_bytes())
        self.assertFalse(any(args[:2] == ["lfs", "fetch"] for args in self.calls))

    def test_download_only_targets_missing_asset_and_materializes_it(self):
        path = self.asset("Content/missing.uasset", content=pointer_for_chunks([self.payload]))
        self.hydrate()
        fetch = next(args for args in self.calls if args[:2] == ["lfs", "fetch"])
        self.assertEqual(["lfs", "fetch", "--include=/Content/missing.uasset", "--exclude="], fetch)
        self.assertEqual(self.payload, path.read_bytes())

    def test_ambiguous_glob_path_fails_without_downloading(self):
        path = self.asset("Content/comma,name.uasset", content=pointer_for_chunks([self.payload]))
        with self.assertRaisesRegex(PreparationError, "safely target"):
            self.hydrate()
        self.assertTrue(path.read_bytes().startswith(b"version https://git-lfs"))
        self.assertFalse(any(args[:2] == ["lfs", "fetch"] for args in self.calls))

    def test_corrupt_same_size_cache_fails_before_fetch_or_checkout(self):
        path = self.asset("missing.uasset", content=pointer_for_chunks([self.payload]), cached=True)
        cached = self.media / self.oid[:2] / self.oid[2:4] / self.oid
        cached.write_bytes(b"x" * len(self.payload))
        with self.assertRaisesRegex(PreparationError, "cached asset is corrupt"):
            self.hydrate()
        self.assertTrue(path.read_bytes().startswith(b"version https://git-lfs"))
        self.assertFalse(any(args[:2] == ["lfs", "fetch"] for args in self.calls))

    def test_preflight_counts_cache_and_checkout_before_download(self):
        self.asset("missing.uasset", content=pointer_for_chunks([self.payload]))
        one_asset_plus_reserve = 1024**3 + len(self.payload)
        usage = shutil._ntuple_diskusage(10**12, 0, one_asset_plus_reserve)
        with patch("portable_pipe_tools.render_farm.lfs_hydration.shutil.disk_usage", return_value=usage):
            with self.assertRaises(InsufficientDiskSpace):
                self.hydrate()
        self.assertFalse(any(args[:2] == ["lfs", "fetch"] for args in self.calls))

    def test_preflight_combines_allocations_on_same_volume(self):
        usage = shutil._ntuple_diskusage(100, 0, 25)
        with patch("portable_pipe_tools.render_farm.lfs_hydration.shutil.disk_usage", return_value=usage):
            with self.assertRaises(InsufficientDiskSpace):
                check_disk_space([(self.root, 10), (self.root / "cache", 10)], reserve_bytes=10)

    def test_preflight_checks_separate_cache_checkout_and_log_volumes(self):
        for full_volume in range(3):
            with self.subTest(full_volume=full_volume):
                paths = [SimpleNamespace(stat=lambda key=key: SimpleNamespace(st_dev=key))
                         for key in range(3)]
                usages = [shutil._ntuple_diskusage(100, 0, 1 if key == full_volume else 100)
                          for key in range(3)]
                with patch("portable_pipe_tools.render_farm.lfs_hydration._existing_parent", side_effect=paths), \
                     patch("portable_pipe_tools.render_farm.lfs_hydration.shutil.disk_usage", side_effect=usages):
                    with self.assertRaises(InsufficientDiskSpace):
                        check_disk_space([(self.root / "cache", 20),
                                          (self.root / "project", 20),
                                          (self.root / "logs", 0)], reserve_bytes=10)

    def test_cache_volume_is_registered_for_runtime_monitoring(self):
        self.asset("ready.uasset")
        monitor = []
        self.hydrate(monitor_paths=monitor.extend)
        self.assertIn(self.media, monitor)

    def test_override_stat_priming_skips_deleted_lfs_paths(self):
        from portable_pipe_tools.render_farm.registered_sync import _prime_override_lfs_stat
        calls = []
        def run(args, cwd=None, capture=False):
            calls.append(args)
            if "ls-files" in args:
                return "deleted.bin\0"
            self.fail("A deleted LFS path must be restored by reset, not renormalized")
        _prime_override_lfs_stat(run, self.root)
        self.assertEqual(1, len(calls))


class CacheFreeFilterTests(unittest.TestCase):
    def test_small_pointer_is_passed_through_and_payload_is_hashed(self):
        payload = b"fake binary content\x00" * 100
        pointer = pointer_for_chunks([payload[:3], payload[3:]])
        self.assertIn(hashlib.sha256(payload).hexdigest().encode(), pointer)
        self.assertEqual(pointer, pointer_for_chunks([pointer]))

    def test_process_protocol_handles_clean_then_smudge(self):
        def block(*items):
            return b"".join(f"{len(item)+4:04x}".encode() + item for item in items) + b"0000"
        payload = b"payload"
        request = (block(b"git-filter-client\n", b"version=2\n")
                   + block(b"capability=clean\n", b"capability=smudge\n")
                   + block(b"command=clean\n", b"pathname=asset.bin\n") + block(payload)
                   + block(b"command=smudge\n", b"pathname=asset.bin\n") + block(payload))
        output = io.BytesIO()
        process_filter(io.BytesIO(request), output)
        self.assertIn(pointer_for_chunks([payload]), output.getvalue())
        self.assertIn(b"000bpayload", output.getvalue())

    def test_real_git_comparison_is_clean_without_recreating_missing_cache(self):
        with tempfile.TemporaryDirectory(prefix="worker-filter-") as temporary:
            root = Path(temporary)
            environment = dict(os.environ, GIT_TERMINAL_PROMPT="0")
            def git(*args):
                result = subprocess.run(["git", "-C", str(root), *args], env=environment,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(0, result.returncode, result.stderr)
                return result.stdout.strip()
            git("init", "-b", "main")
            git("config", "user.name", "Worker test")
            git("config", "user.email", "worker@example.test")
            git("lfs", "install", "--local")
            git("lfs", "track", "*.bin")
            asset = root / "asset.bin"
            asset.write_bytes(b"existing asset\x00" * 100)
            git("add", ".")
            git("commit", "-m", "fixture")
            shutil.rmtree(root / ".git/lfs/objects")
            args = [part for key, value in registered_git_config().items() for part in ("-c", f"{key}={value}")]
            self.assertEqual("", git(*args, "diff", "--exit-code", "HEAD"))
            self.assertFalse((root / ".git/lfs/objects").exists())
            asset.write_bytes(b"modified local asset\x00" * 100)
            self.assertIn("asset.bin", git(*args, "status", "--porcelain"))
            self.assertFalse((root / ".git/lfs/objects").exists())

    def test_real_targeted_fetch_does_not_download_ready_asset_with_same_basename(self):
        from portable_pipe_tools.render_farm.project_workspace import ProjectWorkspace
        with tempfile.TemporaryDirectory(prefix="worker-targeted-lfs-") as temporary:
            root = Path(temporary).resolve()
            source, remote, checkout = (root / name for name in ("source", "remote.git", "checkout"))
            environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file",
                               GIT_LFS_SKIP_SMUDGE="1")
            def git(directory, *args):
                result = subprocess.run(["git", "-C", str(directory), *args], env=environment,
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(0, result.returncode, result.stderr)
                return result.stdout.strip()
            git(root, "init", "--bare", str(remote))
            git(root, "init", "-b", "main", str(source))
            git(source, "config", "user.name", "Worker test")
            git(source, "config", "user.email", "worker@example.test")
            git(source, "lfs", "install", "--local")
            git(source, "lfs", "track", "*.bin")
            ready = b"already complete root asset\x00" * 100
            missing = b"missing nested asset\x00" * 100
            (source / "asset.bin").write_bytes(ready)
            (source / "nested").mkdir()
            (source / "nested/asset.bin").write_bytes(missing)
            git(source, "add", ".")
            git(source, "commit", "-m", "two different LFS assets sharing a basename")
            git(source, "remote", "add", "origin", str(remote))
            git(source, "push", "-u", "origin", "main")
            git(root, "clone", "-b", "main", str(remote), str(checkout))
            (checkout / "asset.bin").write_bytes(ready)
            runner = ProjectWorkspace(root / "logs", git_config=registered_git_config(), discovery_roots=())
            def run(args, cwd=None, capture=False):
                with patch.dict(os.environ, environment):
                    return runner.run(args, cwd or checkout, capture=capture)
            hydrate_registered_assets(run, [checkout], root / "logs", progress=lambda _: None,
                                      check_cancelled=lambda: None)
            ready_oid = hashlib.sha256(ready).hexdigest()
            missing_oid = hashlib.sha256(missing).hexdigest()
            media = checkout / ".git/lfs/objects"
            self.assertEqual(missing, (checkout / "nested/asset.bin").read_bytes())
            self.assertFalse((media / ready_oid[:2] / ready_oid[2:4] / ready_oid).exists())
            self.assertTrue((media / missing_oid[:2] / missing_oid[2:4] / missing_oid).exists())
