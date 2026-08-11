from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.show_manager.shot_manager_core import (
    COLUMN_TITLES,
    EDL_EMPTY_DISPLAY,
    ShotRow,
    apply_edl_sequence_comparison,
    build_updated_sequence_manifest,
    export_edl_updates_to_sequence_manifest,
    format_edl_frame_ranges,
    format_shot_frame_range,
    parse_resolve_edl_xml,
)


def _shot_row(shot_name: str, order: int, is_active: bool) -> ShotRow:
    shot_number = int(shot_name.rsplit("_", 1)[-1])
    return ShotRow(
        order=order,
        sequence="JNG",
        shot_name=shot_name,
        shot_path=Path("JNG") / shot_name,
        section_number=0,
        shot_number=shot_number,
        is_active=is_active,
        manifest_path=Path("jng_sequence_shots_manifest.json"),
        source="manifest",
    )


class ShotManagerEdlTests(unittest.TestCase):
    def test_frame_range_column_precedes_sequence_and_formats_manifest_frames(self) -> None:
        column_keys = list(COLUMN_TITLES)

        self.assertEqual(["move", "shot"], column_keys[:2])
        self.assertEqual(
            column_keys.index("frame_range") + 1,
            column_keys.index("edl_frame_range"),
        )
        self.assertEqual(
            column_keys.index("edl_frame_range") + 1,
            column_keys.index("sequence"),
        )
        self.assertEqual("Frame Range", COLUMN_TITLES["frame_range"])
        self.assertEqual("EDL Frame Range", COLUMN_TITLES["edl_frame_range"])
        self.assertEqual("1001 - 1100", format_shot_frame_range(1001, 1100))
        self.assertEqual(
            f"1001 - {EDL_EMPTY_DISPLAY}",
            format_shot_frame_range(1001, None),
        )
        self.assertEqual(
            EDL_EMPTY_DISPLAY,
            format_shot_frame_range(None, None),
        )
        self.assertEqual(
            "1051 - 1094; 1101 - 1110",
            format_edl_frame_ranges(((1051, 1094), (1101, 1110))),
        )
        self.assertEqual(EDL_EMPTY_DISPLAY, format_edl_frame_ranges(()))

    def test_parse_resolve_xml_uses_timeline_order_and_ignores_return_deduping(self) -> None:
        xml_text = """<?xml version="1.0" encoding="UTF-8"?>
<xmeml version="5">
  <sequence>
    <name>Director Edit</name>
    <media>
      <video>
        <track>
          <clipitem><name>JNG_000_0100.Layer1.mp4</name><start>20</start><end>30</end><in>2</in><out>12</out><enabled>TRUE</enabled></clipitem>
          <clipitem><name>519_TIC_000_0825_beauty_v007.mp4</name><start>5</start><end>10</end><in>5</in><out>10</out><enabled>TRUE</enabled></clipitem>
          <clipitem><name>10000_JNG_000_0050_beauty_v002.mp4</name><start>10</start><end>20</end><in>7</in><out>17</out><enabled>TRUE</enabled></clipitem>
          <clipitem><name>JNG_000_0100.Layer1.mp4</name><start>30</start><end>40</end><in>22</in><out>32</out><enabled>TRUE</enabled></clipitem>
          <clipitem><name>Reference Slate.mp4</name><start>40</start><end>45</end><enabled>TRUE</enabled></clipitem>
        </track>
        <track>
          <clipitem><name>JNG_000_9999.Layer1.mp4</name><start>0</start><end>10</end><enabled>TRUE</enabled></clipitem>
        </track>
      </video>
    </media>
  </sequence>
</xmeml>
"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            xml_path = Path(temporary_directory) / "edit.xml"
            xml_path.write_text(xml_text, encoding="utf-8")
            edl_import = parse_resolve_edl_xml(xml_path)

        self.assertEqual("Director Edit", edl_import.timeline_name)
        self.assertEqual(
            [
                "TIC_000_0825",
                "JNG_000_0050",
                "JNG_000_0100",
                "JNG_000_0100",
            ],
            [occurrence.shot_name for occurrence in edl_import.occurrences],
        )
        self.assertEqual(
            [(5, 10), (7, 17), (2, 12), (22, 32)],
            [
                (occurrence.source_in, occurrence.source_out)
                for occurrence in edl_import.occurrences
            ],
        )
        self.assertEqual(("Reference Slate.mp4",), edl_import.unrecognized_clip_names)

    def test_per_sequence_proposal_numbers_active_then_inactive_shots(self) -> None:
        xml_text = """<xmeml><sequence><name>Edit</name><media><video><track>
<clipitem><name>JNG_000_0100.mp4</name><start>30</start><end>40</end><in>10</in><out>20</out></clipitem>
<clipitem><name>JNG_000_0050.mp4</name><start>10</start><end>20</end><in>5</in><out>15</out></clipitem>
<clipitem><name>JNG_000_0100.mp4</name><start>50</start><end>60</end><in>30</in><out>40</out></clipitem>
</track></video></media></sequence></xmeml>"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            xml_path = Path(temporary_directory) / "edit.xml"
            xml_path.write_text(xml_text, encoding="utf-8")
            edl_import = parse_resolve_edl_xml(xml_path)

        rows = [
            _shot_row("JNG_000_0050", 900, False),
            _shot_row("JNG_000_0100", 905, False),
            _shot_row("JNG_000_0150", 910, True),
        ]
        rows[0].start_frame = 1001
        rows[1].start_frame = 1101
        summary = apply_edl_sequence_comparison(rows, edl_import, "JNG", 201)

        rows_by_name = {row.shot_name: row for row in rows}
        self.assertEqual(201, rows_by_name["JNG_000_0050"].edl_order)
        self.assertEqual(202, rows_by_name["JNG_000_0100"].edl_order)
        self.assertEqual(203, rows_by_name["JNG_000_0150"].edl_order)
        self.assertTrue(rows_by_name["JNG_000_0050"].edl_is_active)
        self.assertTrue(rows_by_name["JNG_000_0100"].edl_is_active)
        self.assertFalse(rows_by_name["JNG_000_0150"].edl_is_active)
        self.assertEqual(
            ((1006, 1015),),
            rows_by_name["JNG_000_0050"].edl_frame_ranges,
        )
        self.assertEqual(
            ((1111, 1120), (1131, 1140)),
            rows_by_name["JNG_000_0100"].edl_frame_ranges,
        )
        self.assertEqual((), rows_by_name["JNG_000_0150"].edl_frame_ranges)
        self.assertEqual(2, summary.active_count)
        self.assertEqual(1, summary.inactive_count)
        self.assertEqual(1, summary.return_cut_count)

    def test_manifest_update_preserves_metadata_and_sets_both_active_fields(self) -> None:
        rows = [
            _shot_row("JNG_000_0050", 900, False),
            _shot_row("JNG_000_0100", 905, True),
        ]
        rows[0].edl_order = 201
        rows[0].edl_is_active = True
        rows[0].edl_frame_ranges = ((1051, 1094),)
        rows[1].edl_order = 202
        rows[1].edl_is_active = False
        manifest = {
            "sequence_name": "JNG",
            "custom_metadata": "preserve me",
            "shot_count": 2,
            "active_shot_count": 1,
            "inactive_shot_count": 1,
            "shots": [
                {
                    "shot_name": "JNG_000_0050",
                    "order": 900,
                    "is_active": False,
                    "is_active_value": 0,
                    "start_frame": 1001,
                    "end_frame": 1100,
                    "level_path": "/Game/LevelA",
                },
                {
                    "shot_name": "JNG_000_0100",
                    "order": 905,
                    "is_active": True,
                    "is_active_value": 1,
                    "level_path": "/Game/LevelB",
                },
            ],
        }

        updated = build_updated_sequence_manifest(manifest, rows, "JNG")

        self.assertEqual("preserve me", updated["custom_metadata"])
        self.assertEqual("/Game/LevelA", updated["shots"][0]["level_path"])
        self.assertEqual(1001, updated["shots"][0]["start_frame"])
        self.assertEqual(1100, updated["shots"][0]["end_frame"])
        self.assertNotIn("edl_frame_ranges", updated["shots"][0])
        self.assertEqual(201, updated["shots"][0]["order"])
        self.assertTrue(updated["shots"][0]["is_active"])
        self.assertEqual(1, updated["shots"][0]["is_active_value"])
        self.assertEqual(202, updated["shots"][1]["order"])
        self.assertFalse(updated["shots"][1]["is_active"])
        self.assertEqual(0, updated["shots"][1]["is_active_value"])
        self.assertEqual(1, updated["active_shot_count"])
        self.assertEqual(1, updated["inactive_shot_count"])
        self.assertEqual(900, manifest["shots"][0]["order"])

    def test_export_writes_stable_updated_file_and_preserves_source(self) -> None:
        rows = [_shot_row("JNG_000_0050", 900, False)]
        rows[0].edl_order = 201
        rows[0].edl_is_active = True
        original_manifest = {
            "sequence_name": "JNG",
            "shots": [
                {
                    "shot_name": "JNG_000_0050",
                    "order": 900,
                    "is_active": False,
                    "is_active_value": 0,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "jng_sequence_shots_manifest.json"
            manifest_path.write_text(
                json.dumps(original_manifest, indent=4) + "\n",
                encoding="utf-8",
            )
            first_export = export_edl_updates_to_sequence_manifest(
                manifest_path,
                rows,
                "JNG",
            )
            source_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            first_updated_data = json.loads(
                first_export.output_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                "jng_sequence_shots_manifest_updated.json",
                first_export.output_path.name,
            )
            self.assertIsNone(first_export.previous_output_backup_path)
            self.assertEqual(900, source_data["shots"][0]["order"])
            self.assertEqual(201, first_updated_data["shots"][0]["order"])

            rows[0].edl_order = 202
            second_export = export_edl_updates_to_sequence_manifest(
                manifest_path,
                rows,
                "JNG",
            )
            self.assertIsNotNone(second_export.previous_output_backup_path)
            assert second_export.previous_output_backup_path is not None
            previous_updated_data = json.loads(
                second_export.previous_output_backup_path.read_text(encoding="utf-8")
            )
            second_updated_data = json.loads(
                second_export.output_path.read_text(encoding="utf-8")
            )
            source_data_after_second_export = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )

        self.assertEqual(201, previous_updated_data["shots"][0]["order"])
        self.assertEqual(202, second_updated_data["shots"][0]["order"])
        self.assertTrue(second_updated_data["shots"][0]["is_active"])
        self.assertEqual(900, source_data_after_second_export["shots"][0]["order"])


if __name__ == "__main__":
    unittest.main()
