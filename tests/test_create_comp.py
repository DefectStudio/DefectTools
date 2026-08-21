from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_pipe_tools.auto_comp_natron.create_comp import (
    CompAlreadyExistsError,
    CompTemplateNotFoundError,
    SmartWriteOutputOptions,
    create_comp,
    get_bundled_template_path,
    get_comp_path,
    get_template_candidates,
)


class CreateCompTests(unittest.TestCase):
    def test_sequence_template_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            sequence_template, fallback_template, _ = get_template_candidates(
                show_root,
                "BSH",
            )
            sequence_template.parent.mkdir(parents=True)
            sequence_template.write_bytes(b"sequence template")
            fallback_template.parent.mkdir(parents=True)
            fallback_template.write_bytes(b"fallback template")

            result = create_comp(show_root, "BSH", "BSH_000_0010")

            self.assertEqual(sequence_template, result.template_path)
            self.assertFalse(result.used_fallback_template)
            self.assertEqual(b"sequence template", result.target_path.read_bytes())

    def test_zzz_template_is_used_when_sequence_template_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            _, fallback_template, _ = get_template_candidates(show_root, "BSH")
            fallback_template.parent.mkdir(parents=True)
            fallback_template.write_bytes(b"fallback template")

            result = create_comp(show_root, "BSH", "BSH_000_0010")

            self.assertEqual(fallback_template, result.template_path)
            self.assertTrue(result.used_fallback_template)
            self.assertEqual(
                get_comp_path(show_root, "BSH", "BSH_000_0010"),
                result.target_path,
            )
            self.assertEqual(b"fallback template", result.target_path.read_bytes())

    def test_bundled_template_is_used_as_the_last_resort(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"

            result = create_comp(show_root, "BSH", "BSH_000_0010")

            self.assertEqual(get_bundled_template_path(), result.template_path)
            self.assertTrue(result.used_fallback_template)
            self.assertTrue(result.target_path.is_file())
            self.assertIn(
                "<boost_serialization",
                result.target_path.read_text(encoding="utf-8"),
            )

    def test_existing_comp_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            target_path = get_comp_path(show_root, "BSH", "BSH_000_0010")
            target_path.parent.mkdir(parents=True)
            target_path.write_bytes(b"artist work")

            with self.assertRaises(CompAlreadyExistsError):
                create_comp(show_root, "BSH", "BSH_000_0010")

            self.assertEqual(b"artist work", target_path.read_bytes())

    def test_copied_natron_project_path_points_to_target_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            _, fallback_template, _ = get_template_candidates(show_root, "BSH")
            fallback_template.parent.mkdir(parents=True)
            fallback_template.write_text(
                "<Project><Name>projectPaths</Name><Value>"
                "&lt;Name&gt;OCIO&lt;/Name&gt;&lt;Value&gt;C:/ocio&lt;/Value&gt;"
                "&lt;Name&gt;Project&lt;/Name&gt;&lt;Value&gt;C:/old/shot/comp/natron&lt;/Value&gt;"
                "</Value></Project>",
                encoding="utf-8",
            )

            result = create_comp(show_root, "BSH", "BSH_000_0010")

            expected = result.target_path.parent.as_posix()
            self.assertIn(
                f"&lt;Name&gt;Project&lt;/Name&gt;&lt;Value&gt;{expected}&lt;/Value&gt;",
                result.target_path.read_text(encoding="utf-8"),
            )

    def test_smart_write_output_choices_are_persisted_in_new_comp(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            _, fallback_template, _ = get_template_candidates(show_root, "BSH")
            fallback_template.parent.mkdir(parents=True)
            fallback_template.write_text(
                "<Project>"
                "<Name>exrOutput</Name><Type>Bool</Type><item><Value>1</Value></item>"
                "<Name>mp4Output</Name><Type>Bool</Type><item><Value>1</Value></item>"
                "<Name>movOutput</Name><Type>Bool</Type><item><Value>0</Value></item>"
                "<Name>heroOutput</Name><Type>Bool</Type><item><Value>1</Value></item>"
                "</Project>",
                encoding="utf-8",
            )

            result = create_comp(
                show_root,
                "BSH",
                "BSH_000_0010",
                smart_write_outputs=SmartWriteOutputOptions(
                    exr=False,
                    mp4=False,
                    mov=True,
                    hero=True,
                ),
            )

            project_text = result.target_path.read_text(encoding="utf-8")
            expected_values = {
                "exrOutput": 0,
                "mp4Output": 0,
                "movOutput": 1,
                "heroOutput": 1,
            }
            for parameter_name, expected_value in expected_values.items():
                self.assertIn(
                    f"<Name>{parameter_name}</Name><Type>Bool</Type>"
                    f"<item><Value>{expected_value}</Value>",
                    project_text,
                )

    def test_missing_templates_report_all_checked_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            show_root = Path(temporary_directory) / "show"
            expected_candidates = (
                show_root / "missing-sequence-template.ntp",
                show_root / "missing-show-template.ntp",
                show_root / "missing-bundled-template.ntp",
            )

            with patch(
                "portable_pipe_tools.auto_comp_natron.create_comp.create_comp."
                "get_template_candidates",
                return_value=expected_candidates,
            ):
                with self.assertRaises(CompTemplateNotFoundError) as context:
                    create_comp(show_root, "BSH", "BSH_000_0010")

            self.assertEqual(expected_candidates, context.exception.candidates)

    def test_shot_must_belong_to_selected_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                create_comp(
                    Path(temporary_directory) / "show",
                    "BSH",
                    "EXF_000_0010",
                )


if __name__ == "__main__":
    unittest.main()
