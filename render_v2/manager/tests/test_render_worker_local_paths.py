from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.local_paths import (
    OVERWRITE_EXISTING_EXR_FIELD,
    OVERWRITE_EXISTING_MP4_FIELD,
    derive_show_file_server_path,
    find_existing_output_targets,
    prepare_worker_output_mapping,
    resolve_worker_output_directory,
)


class RenderWorkerLocalPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.show_root = self.root / "Local Dropbox" / "defect" / "s3bishop"
        self.farm_root = self.show_root / "renderFarm"
        self.farm_root.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _job(self) -> dict[str, object]:
        return {
            "project": "s3bishop",
            "shot_name": "BSH_000_0030",
            "render_version": 17,
            "output_directory": (
                "F:/Defect Dropbox/defect/s3bishop/sequences/BSH/"
                "BSH_000_0030/lite/unreal/_output"
            ),
            "submitted_show_file_server_path": (
                "F:/Defect Dropbox/defect/s3bishop"
            ),
            "output_relative_directory": (
                "sequences/BSH/BSH_000_0030/lite/unreal/_output"
            ),
            "output_file_name_format": (
                "BSH_000_0030_beauty_v017/"
                "BSH_000_0030_beauty_v017.{frame_number}"
            ),
            "mp4_file_name_format": "BSH_000_0030_beauty_v017",
            "outputs": {"mp4": True, "exr": True, "hero": True},
        }

    def test_derives_show_path_from_render_farm_folder(self) -> None:
        self.assertEqual(
            derive_show_file_server_path(self.farm_root),
            self.show_root,
        )

    def test_render_farm_folder_must_be_named_render_farm(self) -> None:
        wrong_folder = self.show_root / "farm"
        wrong_folder.mkdir()
        with self.assertRaisesRegex(ValueError, "folder named 'renderFarm'"):
            derive_show_file_server_path(wrong_folder)

    def test_resolves_explicit_portable_output_path(self) -> None:
        output, relative = resolve_worker_output_directory(
            self._job(),
            self.show_root,
        )
        self.assertEqual(
            output,
            self.show_root
            / "sequences"
            / "BSH"
            / "BSH_000_0030"
            / "lite"
            / "unreal"
            / "_output",
        )
        self.assertEqual(
            relative,
            "sequences/BSH/BSH_000_0030/lite/unreal/_output",
        )

    def test_legacy_job_infers_path_after_project_folder(self) -> None:
        job = self._job()
        job.pop("output_relative_directory")
        job.pop("submitted_show_file_server_path")
        output, relative = resolve_worker_output_directory(job, self.show_root)
        self.assertEqual(output.parent.name, "unreal")
        self.assertEqual(
            relative,
            "sequences/BSH/BSH_000_0030/lite/unreal/_output",
        )

    def test_prepare_records_submitted_and_worker_paths(self) -> None:
        job = self._job()
        mapping = prepare_worker_output_mapping(job, self.farm_root)
        self.assertEqual(
            job["submitted_output_directory"],
            "F:/Defect Dropbox/defect/s3bishop/sequences/BSH/"
            "BSH_000_0030/lite/unreal/_output",
        )
        self.assertEqual(job["output_directory"], str(mapping.worker_output_directory))
        self.assertEqual(
            job["worker_show_file_server_path"],
            str(self.show_root),
        )
        self.assertTrue(mapping.worker_output_directory.is_dir())

    def test_existing_mp4_is_reported_as_collision(self) -> None:
        job = self._job()
        job[OVERWRITE_EXISTING_MP4_FIELD] = False
        output, _ = resolve_worker_output_directory(job, self.show_root)
        output.mkdir(parents=True)
        mp4 = output / "BSH_000_0030_beauty_v017.mp4"
        mp4.write_bytes(b"render")
        self.assertEqual(find_existing_output_targets(job, output), [mp4])
        with self.assertRaisesRegex(FileExistsError, "Choose a new render version"):
            prepare_worker_output_mapping(job, self.farm_root)

    def test_explicit_mp4_overwrite_removes_only_the_existing_mp4(self) -> None:
        job = self._job()
        job[OVERWRITE_EXISTING_MP4_FIELD] = True
        output, _ = resolve_worker_output_directory(job, self.show_root)
        output.mkdir(parents=True)
        mp4 = output / "BSH_000_0030_beauty_v017.mp4"
        mp4.write_bytes(b"old render")

        mapping = prepare_worker_output_mapping(job, self.farm_root)

        self.assertEqual(output, mapping.worker_output_directory)
        self.assertFalse(mp4.exists())

    def test_mp4_is_not_removed_when_an_existing_exr_folder_blocks_job(self) -> None:
        job = self._job()
        job[OVERWRITE_EXISTING_MP4_FIELD] = True
        job[OVERWRITE_EXISTING_EXR_FIELD] = False
        output, _ = resolve_worker_output_directory(job, self.show_root)
        output.mkdir(parents=True)
        mp4 = output / "BSH_000_0030_beauty_v017.mp4"
        mp4.write_bytes(b"old render")
        exr_folder = output / "BSH_000_0030_beauty_v017"
        exr_folder.mkdir()
        (exr_folder / "BSH_000_0030_beauty_v017.1001.exr").write_bytes(
            b"render"
        )

        with self.assertRaisesRegex(FileExistsError, "Existing target"):
            prepare_worker_output_mapping(job, self.farm_root)

        self.assertTrue(mp4.exists())

    def test_legacy_job_defaults_to_overwriting_mp4_and_exr_folder(self) -> None:
        job = self._job()
        output, _ = resolve_worker_output_directory(job, self.show_root)
        output.mkdir(parents=True)
        mp4 = output / "BSH_000_0030_beauty_v017.mp4"
        mp4.write_bytes(b"old render")
        exr_folder = output / "BSH_000_0030_beauty_v017"
        exr_folder.mkdir()
        (exr_folder / "BSH_000_0030_beauty_v017.1001.exr").write_bytes(
            b"render"
        )

        mapping = prepare_worker_output_mapping(job, self.farm_root)

        self.assertEqual(output, mapping.worker_output_directory)
        self.assertFalse(mp4.exists())
        self.assertFalse(exr_folder.exists())

    def test_existing_exr_version_folder_is_reported_as_collision(self) -> None:
        job = self._job()
        output, _ = resolve_worker_output_directory(job, self.show_root)
        exr_folder = output / "BSH_000_0030_beauty_v017"
        exr_folder.mkdir(parents=True)
        (exr_folder / "BSH_000_0030_beauty_v017.1001.exr").write_bytes(b"render")
        self.assertEqual(find_existing_output_targets(job, output), [exr_folder])

    def test_rejects_relative_path_that_escapes_show_root(self) -> None:
        job = self._job()
        job["output_relative_directory"] = "../another_show/output"
        with self.assertRaisesRegex(ValueError, "escapes the show folder"):
            resolve_worker_output_directory(job, self.show_root)


if __name__ == "__main__":
    unittest.main()
