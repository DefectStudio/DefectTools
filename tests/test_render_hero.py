from __future__ import annotations

import ast
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools import render_hero


TEST_ROOT = Path(r"I:\AICache\manual-render-hero-chooser-dev\tests")
REPOSITORY = Path(__file__).resolve().parents[1]


def contents(folder: Path) -> dict[str, bytes | None]:
    return {str(path.relative_to(folder)): None if path.is_dir() else path.read_bytes()
            for path in folder.rglob("*")}


class RenderHeroTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="case-", dir=TEST_ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.dropbox = self.root / "defect"
        self.sequence = self.dropbox / "spectrum" / "sequences" / "SPE"
        self.shot = self.sequence / "SPE_000_0050"
        self.output = self.shot / "lite" / "unreal" / "_output"
        self.source = self.output / "SPE_000_0050_beauty_v046"
        self.source.mkdir(parents=True)
        self.hero = self.output / "_hero"

    def frame(self, name: str = "SPE_000_0050_beauty_v046.1001.exr", data: bytes = b"exr-data") -> Path:
        path = self.source / name
        path.write_bytes(data)
        return path

    def old_hero(self) -> dict[str, bytes | None]:
        self.hero.mkdir()
        (self.hero / "SPE_000_0050.0999.exr").write_bytes(b"old frame")
        (self.hero / "old-subfolder").mkdir()
        (self.hero / "old-subfolder" / "notes.txt").write_text("old nested content")
        return contents(self.hero)

    def test_discovery_filters_support_folders_keeps_empty_shots_and_sorts_numeric_versions(self) -> None:
        self.frame()
        for version in (2, 9, 1000):
            folder = self.output / f"SPE_000_0050_beauty_v{version:03d}"
            folder.mkdir()
            (folder / f"SPE_000_0050_beauty_v{version:03d}.1001.EXR").write_bytes(b"frame")
        (self.output / "SPE_000_0050_beauty_v1001").mkdir()
        no_exrs = self.output / "SPE_000_0050_beauty_v9999"
        no_exrs.mkdir()
        (no_exrs / "preview.png").write_bytes(b"preview")
        self.hero.mkdir()
        (self.hero / "SPE_000_0050.1001.exr").write_bytes(b"current hero")
        (self.sequence / "SPE_000_0100").mkdir()
        (self.sequence / "_output").mkdir()
        (self.sequence / "notes").mkdir()
        (self.dropbox / "CacheClip").mkdir()
        (self.dropbox / "spectrum" / "sequences" / "audio").mkdir()
        (self.dropbox / "spectrum" / "sequences" / "_output").mkdir()
        (self.dropbox / "spectrum" / "sequences" / "EMPTY").mkdir()

        self.assertEqual([path.name for path in render_hero.discover_shows(self.dropbox)], ["spectrum"])
        self.assertEqual([path.name for path in render_hero.discover_sequences(self.dropbox / "spectrum")],
                         ["EMPTY", "SPE"])
        shots = render_hero.discover_shots(self.sequence)
        self.assertEqual([shot.name for shot in shots], ["SPE_000_0050", "SPE_000_0100"])
        self.assertEqual([version.version for version in shots[0].versions], [1000, 46, 9, 2])
        self.assertEqual([version.frame_count for version in shots[0].versions], [1, 1, 1, 1])
        self.assertEqual(shots[1].versions, ())

    def test_naming_matches_actual_unreal_callback_without_importing_unreal(self) -> None:
        callback = REPOSITORY / "Unreal/DefectToolsDev/Plugins/QuickWidgetTools/Content/Python/mrg_callbacks_hero.py"
        tree = ast.parse(callback.read_text(encoding="utf-8"))
        hero_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MRGHero")
        method = next(node for node in hero_class.body if isinstance(node, ast.FunctionDef)
                      and node.name == "_make_hero_filename")
        method.decorator_list = []
        namespace = {"os": os, "re": re}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(callback), "exec"), namespace)
        for name in ("SPE_000_0050_beauty_v046.1001.exr", "SPE_000_0050_environment_v1000.000001.EXR",
                     "SPE_000_0050.1001.exr", "SPE_000_0050_beauty_v001.exr", "simple.1001.exr",
                     "SPE_000_0050_beauty_v046.1001.png", "SPE_000_0050_beauty_v046.-001.exr"):
            with self.subTest(name=name):
                self.assertEqual(render_hero.make_hero_filename(name), namespace["_make_hero_filename"](None, name))

    def test_promotion_removes_obsolete_hero_content_and_preserves_all_source_files(self) -> None:
        self.frame()
        self.frame("SPE_000_0050_beauty_v046.1002.exr", b"second exr")
        (self.source / "preview.png").write_bytes(b"preview")
        (self.source / "RenderLog.txt").write_text("render log")
        self.old_hero()
        original = contents(self.source)
        progress = []
        real_copy = shutil.copy2
        copies = []

        def direct_copy(source, destination, *args, **kwargs):
            self.assertEqual(Path(source).parent, self.source)
            self.assertEqual(Path(destination).parent, self.hero)
            if not copies:
                self.assertEqual(list(self.hero.iterdir()), [], "Hero must be emptied before the first EXR copy")
            copies.append((Path(source), Path(destination)))
            return real_copy(source, destination, *args, **kwargs)

        with patch.object(render_hero.shutil, "copy2", side_effect=direct_copy), \
                patch.object(shutil, "copytree", side_effect=AssertionError("No backup copy is allowed")), \
                patch.object(tempfile, "mkdtemp", side_effect=AssertionError("No staging folder is allowed")), \
                patch.object(shutil, "disk_usage", side_effect=AssertionError("No scratch capacity check is needed")):
            result = render_hero.promote_render(self.source,
                progress=lambda done, total, message: progress.append((done, total, message)))
        self.assertEqual(result.source_path, self.source)
        self.assertEqual(result.hero_path, self.hero)
        self.assertEqual(result.copied_count, 2)
        self.assertEqual(contents(self.hero), {"SPE_000_0050.1001.exr": b"exr-data", "SPE_000_0050.1002.exr": b"second exr"})
        self.assertEqual(contents(self.source), original)
        self.assertEqual(copies, [
            (self.source / "SPE_000_0050_beauty_v046.1001.exr", self.hero / "SPE_000_0050.1001.exr"),
            (self.source / "SPE_000_0050_beauty_v046.1002.exr", self.hero / "SPE_000_0050.1002.exr"),
        ])
        self.assertEqual(set(self.output.iterdir()), {self.source, self.hero})
        self.assertEqual(progress[-1][:2], (2, 2))

    def test_promotion_creates_missing_hero(self) -> None:
        self.frame()
        render_hero.promote_render(self.source)
        self.assertEqual(contents(self.hero), {"SPE_000_0050.1001.exr": b"exr-data"})

    def test_empty_missing_or_malformed_sources_leave_existing_hero_unchanged(self) -> None:
        original = self.old_hero()
        with self.assertRaisesRegex(ValueError, "No EXR frames"):
            render_hero.promote_render(self.source)
        self.assertEqual(contents(self.hero), original)
        self.frame(data=b"")
        with self.assertRaisesRegex(ValueError, "EXR is empty"):
            render_hero.promote_render(self.source)
        self.assertEqual(contents(self.hero), original)
        (self.source / "SPE_000_0050_beauty_v046.1001.exr").unlink()
        self.frame("OTHER_000_0050_beauty_v046.1001.exr")
        with self.assertRaisesRegex(ValueError, "does not match this shot"):
            render_hero.promote_render(self.source)
        self.assertEqual(contents(self.hero), original)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            render_hero.promote_render(self.output / "SPE_000_0050_beauty_v999")
        self.assertEqual(contents(self.hero), original)

    def test_filename_collisions_leave_existing_hero_unchanged(self) -> None:
        self.frame()
        self.frame("SPE_000_0050_environment_v046.1001.exr", b"other pass")
        original = self.old_hero()
        with self.assertRaisesRegex(ValueError, "same hero frame"):
            render_hero.promote_render(self.source)
        self.assertEqual(contents(self.hero), original)

    def test_copy_failure_keeps_completed_new_frames_without_restoring_previous_hero(self) -> None:
        self.frame()
        self.frame("SPE_000_0050_beauty_v046.1002.exr", b"second exr")
        self.old_hero()
        source_before = contents(self.source)
        real_copy = shutil.copy2

        def fail_second_install(source, destination, *args, **kwargs):
            target = Path(destination)
            if target.parent == self.hero and target.name == "SPE_000_0050.1002.exr":
                raise OSError("injected destination write failure")
            return real_copy(source, destination, *args, **kwargs)

        with patch.object(render_hero.shutil, "copy2", side_effect=fail_second_install), \
                patch.object(shutil, "copytree", side_effect=AssertionError("No backup or restore is allowed")):
            with self.assertRaisesRegex(RuntimeError, "Hero copy stopped after 1/2 frames"):
                render_hero.promote_render(self.source)
        self.assertEqual(contents(self.hero), {"SPE_000_0050.1001.exr": b"exr-data"})
        self.assertEqual(contents(self.source), source_before)
        self.assertEqual(set(self.output.iterdir()), {self.source, self.hero})

    def test_rejects_wrong_scope(self) -> None:
        self.frame()
        original = self.old_hero()
        with self.assertRaisesRegex(ValueError, "versioned render"):
            render_hero.promote_render(self.hero)
        with self.assertRaisesRegex(ValueError, "versioned render"):
            render_hero.promote_render(self.root / "comp" / self.source.name)
        self.assertEqual(contents(self.hero), original)

    def test_rejects_linked_source_without_touching_link_target(self) -> None:
        self.frame()
        link = self.output / "SPE_000_0050_beauty_v047"
        try:
            link.symlink_to(self.source, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Directory symlink privilege unavailable: {exc}")
        original = self.old_hero()
        with self.assertRaisesRegex(ValueError, "Linked folders"):
            render_hero.promote_render(link)
        self.assertEqual(contents(self.hero), original)
        self.assertEqual((self.source / "SPE_000_0050_beauty_v046.1001.exr").read_bytes(), b"exr-data")


if __name__ == "__main__":
    unittest.main()
