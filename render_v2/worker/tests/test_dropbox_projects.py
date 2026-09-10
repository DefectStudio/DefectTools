from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.dropbox_projects import list_dropbox_projects


class DropboxProjectTests(unittest.TestCase):
    def test_only_immediate_shows_with_farm_preserve_exact_folder_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in ("Development/renderFarm", "s3bishop/RenderFarm",
                           "Show With Spaces/renderFarm", "Other/nested/renderFarm"):
                (root / folder).mkdir(parents=True)
            (root / "readme.txt").write_text("ignored")
            projects = list_dropbox_projects(root)
            self.assertEqual(["Development", "s3bishop", "Show With Spaces"], list(projects))
            self.assertEqual(root / "s3bishop/RenderFarm", projects["s3bishop"])
            self.assertEqual([], list((root / "Development/renderFarm").iterdir()))

    def test_missing_root_is_reported_and_empty_root_is_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual({}, list_dropbox_projects(root))
            with self.assertRaisesRegex(FileNotFoundError, "unavailable"):
                list_dropbox_projects(root / "missing")

