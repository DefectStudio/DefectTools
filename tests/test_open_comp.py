from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from portable_pipe_tools.auto_comp_natron.create_comp import (
    get_comp_path,
    get_template_candidates,
)
from portable_pipe_tools.auto_comp_natron.open_comp import (
    CompNotFoundError,
    create_and_open_comp,
    open_comp,
)


class OpenCompTests(unittest.TestCase):
    def test_open_comp_opens_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            comp_path.parent.mkdir(parents=True)
            comp_path.write_bytes(b"comp")
            opener = Mock()

            result = open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
            )

            opener.assert_called_once_with(comp_path)
            self.assertEqual(comp_path, result.comp_path)
            self.assertFalse(result.created)

    def test_open_comp_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            opener = Mock()

            with self.assertRaises(CompNotFoundError):
                open_comp(
                    show_root,
                    "BSH",
                    "BSH_000_0010",
                    opener=opener,
                )

            opener.assert_not_called()

    def test_create_and_open_creates_missing_comp_then_opens_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            _, fallback_template = get_template_candidates(show_root, "BSH")
            fallback_template.parent.mkdir(parents=True)
            fallback_template.write_bytes(b"template")
            opener = Mock()

            result = create_and_open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
            )

            self.assertTrue(result.created)
            self.assertEqual(b"template", result.comp_path.read_bytes())
            opener.assert_called_once_with(result.comp_path)

    def test_create_and_open_opens_existing_comp_without_changing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            comp_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            comp_path.parent.mkdir(parents=True)
            comp_path.write_bytes(b"artist work")
            opener = Mock()

            result = create_and_open_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                opener=opener,
            )

            self.assertFalse(result.created)
            self.assertEqual(b"artist work", comp_path.read_bytes())
            opener.assert_called_once_with(comp_path)


if __name__ == "__main__":
    unittest.main()
