from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest


DEFAULT_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "Content"
    / "Python"
    / "set_frame_range.py"
)
SCRIPT_PATH = Path(os.environ.get("SET_FRAME_RANGE_SCRIPT_PATH", DEFAULT_SCRIPT_PATH))


class FakeMovieSceneSubSection:
    def __init__(
        self,
        start_frame: int,
        exclusive_end_frame: int,
        sequence: FakeLevelSequence | None = None,
    ) -> None:
        self.start_frame = start_frame
        self.exclusive_end_frame = exclusive_end_frame
        self.sequence = sequence
        self.parameters = SimpleNamespace(
            start_frame_offset=0,
            first_loop_start_frame_offset=0,
            end_frame_offset=0,
            time_scale=1.0,
        )

    def get_sequence(self) -> FakeLevelSequence | None:
        return self.sequence

    def get_start_frame(self) -> int:
        return self.start_frame

    def get_end_frame(self) -> int:
        return self.exclusive_end_frame

    def set_range(self, start_frame: int, exclusive_end_frame: int) -> None:
        self.start_frame = start_frame
        self.exclusive_end_frame = exclusive_end_frame

    def get_editor_property(self, property_name: str) -> object:
        if property_name == "parameters":
            return self.parameters
        raise AttributeError(property_name)

    def set_editor_property(self, property_name: str, value: object) -> None:
        if property_name != "parameters":
            raise AttributeError(property_name)
        self.parameters = value

    def get_name(self) -> str:
        return "AlreadyCorrectSubSection"


class FakeDirectPropertySubSection(FakeMovieSceneSubSection):
    def __init__(self, start_frame: int, exclusive_end_frame: int) -> None:
        super().__init__(start_frame, exclusive_end_frame)
        self.direct_properties = {
            "start_frame_offset": 3,
            "first_loop_start_frame_offset": 4,
            "end_frame_offset": 5,
            "time_scale": 0.5,
        }

    def get_editor_property(self, property_name: str) -> object:
        if property_name == "parameters":
            raise AttributeError(property_name)
        if property_name in self.direct_properties:
            return self.direct_properties[property_name]
        return super().get_editor_property(property_name)

    def set_editor_property(self, property_name: str, value: object) -> None:
        if property_name == "parameters":
            raise AttributeError(property_name)
        if property_name in self.direct_properties:
            self.direct_properties[property_name] = value
            return
        super().set_editor_property(property_name, value)


class FakeTrack:
    def __init__(self, sections: list[FakeMovieSceneSubSection]) -> None:
        self.sections = sections

    def get_sections(self) -> list[FakeMovieSceneSubSection]:
        return self.sections


class FakeLevelSequence:
    def __init__(
        self,
        start_frame: int,
        exclusive_end_frame: int,
        path_name: str = "/Game/_S3Bishop/Sequences/TIC/TIC_000_0450",
        subsections: list[FakeMovieSceneSubSection] | None = None,
        shot_subsections: list[FakeMovieSceneSubSection] | None = None,
        camera_cut_sections: list[FakeMovieSceneSubSection] | None = None,
        playback_range_locked: bool = False,
    ) -> None:
        self.start_frame = start_frame
        self.exclusive_end_frame = exclusive_end_frame
        self.path_name = path_name
        self.subsections = subsections or []
        self.shot_subsections = shot_subsections or []
        self.camera_cut_sections = camera_cut_sections or []
        self.playback_range_locked = playback_range_locked

    def find_tracks_by_type(self, track_type: object) -> list[object]:
        track_name = getattr(track_type, "__name__", "")
        if track_name == "MovieSceneSubTrack" and self.subsections:
            return [FakeTrack(self.subsections)]
        if track_name == "MovieSceneCinematicShotTrack" and self.shot_subsections:
            return [FakeTrack(self.shot_subsections)]
        if track_name == "MovieSceneCameraCutTrack" and self.camera_cut_sections:
            return [FakeTrack(self.camera_cut_sections)]
        return []

    def get_playback_start(self) -> int:
        return self.start_frame

    def get_playback_end(self) -> int:
        return self.exclusive_end_frame

    def is_playback_range_locked(self) -> bool:
        return self.playback_range_locked

    def set_playback_range_locked(self, locked: bool) -> None:
        self.playback_range_locked = locked

    def set_playback_start(self, start_frame: int) -> None:
        self.start_frame = start_frame

    def set_playback_end(self, exclusive_end_frame: int) -> None:
        self.exclusive_end_frame = exclusive_end_frame

    def get_name(self) -> str:
        return self.path_name.rsplit("/", 1)[-1]

    def get_path_name(self) -> str:
        return self.path_name


class FakeShotDataAsset:
    def __init__(self, start_frame: int, end_frame: int) -> None:
        self.properties = {
            "StartFrame": start_frame,
            "EndFrame": end_frame,
        }

    def get_editor_property(self, property_name: str) -> int:
        return self.properties[property_name]

    def set_editor_property(self, property_name: str, value: int) -> None:
        self.properties[property_name] = value


class UnrealBoundary(ModuleType):
    MASTER_PATH = "/Game/_S3Bishop/Sequences/TIC/TIC_000_0450"
    DATA_PATH = (
        "/Game/_S3Bishop/Sequences/TIC/TIC_000_0450/"
        "TIC_000_0450_Data.TIC_000_0450_Data"
    )
    SUBSEQUENCES_PATH = (
        "/Game/_S3Bishop/Sequences/TIC/TIC_000_0450/SubSequences"
    )
    CHILD_PATH = (
        "/Game/_S3Bishop/Sequences/TIC/TIC_000_0450/SubSequences/ANM/"
        "TIC_000_0450_ANM_v001"
    )

    def __init__(self) -> None:
        super().__init__("unreal")
        self.master = FakeLevelSequence(0, 101)
        self.data_asset = FakeShotDataAsset(0, 100)
        self.child: FakeLevelSequence | None = None
        self.loaded_paths: list[str] = []
        self.saved_assets: list[object] = []

        self.LevelSequence = FakeLevelSequence
        self.MovieSceneSubSection = FakeMovieSceneSubSection
        self.MovieSceneSubTrack = type("MovieSceneSubTrack", (), {})
        self.MovieSceneCinematicShotTrack = type(
            "MovieSceneCinematicShotTrack", (), {}
        )
        self.MovieSceneLevelVisibilityTrack = type(
            "MovieSceneLevelVisibilityTrack", (), {}
        )
        self.MovieSceneCameraCutTrack = type("MovieSceneCameraCutTrack", (), {})
        self.FrameNumber = int
        self.EditorAssetLibrary = SimpleNamespace(
            does_asset_exist=self.does_asset_exist,
            does_directory_exist=self.does_directory_exist,
            list_assets=self.list_assets,
            load_asset=self.load_asset,
            save_loaded_asset=self.save_loaded_asset,
        )
        self.LevelSequenceEditorBlueprintLibrary = SimpleNamespace(
            refresh_current_level_sequence=lambda: None
        )

    def does_asset_exist(self, asset_path: str) -> bool:
        return asset_path in {self.MASTER_PATH, self.DATA_PATH, self.CHILD_PATH}

    def does_directory_exist(self, directory_path: str) -> bool:
        return self.child is not None and directory_path == self.SUBSEQUENCES_PATH

    def list_assets(
        self,
        directory_path: str,
        recursive: bool = False,
        include_folder: bool = False,
    ) -> list[str]:
        del recursive, include_folder
        if self.child is not None and directory_path == self.SUBSEQUENCES_PATH:
            return [self.CHILD_PATH]
        return []

    def load_asset(self, asset_path: str) -> object | None:
        self.loaded_paths.append(asset_path)
        if asset_path == self.MASTER_PATH:
            return self.master
        if asset_path == self.DATA_PATH:
            return self.data_asset
        if asset_path == self.CHILD_PATH:
            return self.child
        return None

    def save_loaded_asset(self, asset: object) -> bool:
        self.saved_assets.append(asset)
        return True

    def add_already_correct_child(self, requested_end_frame: int) -> None:
        exclusive_end_frame = requested_end_frame + 1
        self.child = FakeLevelSequence(
            0,
            exclusive_end_frame,
            path_name=self.CHILD_PATH,
            subsections=[FakeMovieSceneSubSection(0, exclusive_end_frame)],
        )

    @staticmethod
    def log(_message: str) -> None:
        pass

    @staticmethod
    def log_warning(_message: str) -> None:
        pass

    @staticmethod
    def log_error(_message: str) -> None:
        pass


def load_set_frame_range(unreal_boundary: UnrealBoundary):
    sys.modules["unreal"] = unreal_boundary
    spec = importlib.util.spec_from_file_location(
        "set_frame_range_under_test", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SetFrameRangeTests(unittest.TestCase):
    def test_unchanged_request_checks_sequences_without_saving(self) -> None:
        unreal_boundary = UnrealBoundary()
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            100,
        )

        self.assertTrue(result)
        self.assertIn(UnrealBoundary.MASTER_PATH, unreal_boundary.loaded_paths)
        self.assertEqual([], unreal_boundary.saved_assets)

    def test_changed_request_saves_only_assets_that_need_changes(self) -> None:
        unreal_boundary = UnrealBoundary()
        unreal_boundary.add_already_correct_child(requested_end_frame=110)
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            110,
        )

        self.assertTrue(result)
        self.assertEqual(111, unreal_boundary.master.exclusive_end_frame)
        self.assertEqual(110, unreal_boundary.data_asset.properties["EndFrame"])
        self.assertIn(unreal_boundary.master, unreal_boundary.saved_assets)
        self.assertIn(unreal_boundary.data_asset, unreal_boundary.saved_assets)
        self.assertNotIn(unreal_boundary.child, unreal_boundary.saved_assets)

    def test_changed_request_saves_a_child_with_nonzero_timing_offsets(self) -> None:
        unreal_boundary = UnrealBoundary()
        unreal_boundary.add_already_correct_child(requested_end_frame=110)
        child_section = unreal_boundary.child.subsections[0]
        child_section.parameters.start_frame_offset = 5
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            110,
        )

        self.assertTrue(result)
        self.assertIn(unreal_boundary.child, unreal_boundary.saved_assets)
        self.assertEqual(0, child_section.parameters.start_frame_offset)

    def test_matching_data_range_reconciles_divergent_sequence_assets(self) -> None:
        unreal_boundary = UnrealBoundary()
        unreal_boundary.master.exclusive_end_frame = 91
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            100,
        )

        self.assertTrue(result)
        self.assertEqual(101, unreal_boundary.master.exclusive_end_frame)
        self.assertEqual([unreal_boundary.master], unreal_boundary.saved_assets)

    def test_matching_data_range_aligns_and_unlocks_child_playback(self) -> None:
        unreal_boundary = UnrealBoundary()
        child = FakeLevelSequence(
            12,
            70,
            path_name=UnrealBoundary.CHILD_PATH,
            playback_range_locked=True,
        )
        unreal_boundary.child = child
        unreal_boundary.master.subsections = [
            FakeMovieSceneSubSection(0, 101, child)
        ]
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            100,
        )

        self.assertTrue(result)
        self.assertEqual(0, child.start_frame)
        self.assertEqual(101, child.exclusive_end_frame)
        self.assertFalse(child.playback_range_locked)
        self.assertEqual([child], unreal_boundary.saved_assets)

    def test_matching_data_range_clamps_child_camera_cuts(self) -> None:
        unreal_boundary = UnrealBoundary()
        camera_cut = FakeMovieSceneSubSection(15, 75)
        child = FakeLevelSequence(
            0,
            101,
            path_name=UnrealBoundary.CHILD_PATH,
            camera_cut_sections=[camera_cut],
        )
        unreal_boundary.child = child
        unreal_boundary.master.subsections = [
            FakeMovieSceneSubSection(0, 101, child)
        ]
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            100,
        )

        self.assertTrue(result)
        self.assertEqual(0, camera_cut.start_frame)
        self.assertEqual(101, camera_cut.exclusive_end_frame)
        self.assertEqual([child], unreal_boundary.saved_assets)

    def test_repeating_a_successful_change_triggers_no_additional_saves(self) -> None:
        unreal_boundary = UnrealBoundary()
        set_frame_range = load_set_frame_range(unreal_boundary)

        first_result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            110,
        )
        self.assertTrue(first_result)

        unreal_boundary.loaded_paths.clear()
        unreal_boundary.saved_assets.clear()

        second_result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            110,
        )

        self.assertTrue(second_result)
        self.assertIn(UnrealBoundary.MASTER_PATH, unreal_boundary.loaded_paths)
        self.assertEqual([], unreal_boundary.saved_assets)

    def test_master_subsections_supports_sub_and_cinematic_shot_tracks(self) -> None:
        unreal_boundary = UnrealBoundary()
        sub_track_section = FakeMovieSceneSubSection(0, 101)
        shot_track_section = FakeMovieSceneSubSection(0, 101)
        unreal_boundary.master.subsections = [sub_track_section]
        unreal_boundary.master.shot_subsections = [shot_track_section]
        set_frame_range = load_set_frame_range(unreal_boundary)

        sections = set_frame_range._master_subsections(unreal_boundary.master)

        self.assertEqual([sub_track_section, shot_track_section], sections)

    def test_run_reconciles_sub_and_cinematic_shot_track_sections(self) -> None:
        unreal_boundary = UnrealBoundary()
        sub_track_section = FakeMovieSceneSubSection(5, 80)
        sub_track_section.parameters.start_frame_offset = 3
        sub_track_section.parameters.first_loop_start_frame_offset = 4
        sub_track_section.parameters.end_frame_offset = 5
        sub_track_section.parameters.time_scale = 0.5
        shot_track_section = FakeMovieSceneSubSection(10, 90)
        unreal_boundary.master.subsections = [sub_track_section]
        unreal_boundary.master.shot_subsections = [shot_track_section]
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            100,
        )

        self.assertTrue(result)
        for section in (sub_track_section, shot_track_section):
            self.assertEqual(0, section.start_frame)
            self.assertEqual(101, section.exclusive_end_frame)
        self.assertEqual(0, sub_track_section.parameters.start_frame_offset)
        self.assertEqual(0, sub_track_section.parameters.first_loop_start_frame_offset)
        self.assertEqual(0, sub_track_section.parameters.end_frame_offset)
        self.assertEqual(1.0, sub_track_section.parameters.time_scale)
        self.assertEqual([unreal_boundary.master], unreal_boundary.saved_assets)

    def test_run_uses_direct_property_fallback_for_subsection_timing(self) -> None:
        unreal_boundary = UnrealBoundary()
        section = FakeDirectPropertySubSection(0, 101)
        unreal_boundary.master.subsections = [section]
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            100,
        )

        self.assertTrue(result)
        self.assertEqual(
            {
                "start_frame_offset": 0,
                "first_loop_start_frame_offset": 0,
                "end_frame_offset": 0,
                "time_scale": 1.0,
            },
            section.direct_properties,
        )
        self.assertEqual([unreal_boundary.master], unreal_boundary.saved_assets)

    def test_reconciles_recursive_subsections_offsets_locks_and_camera_cuts(self) -> None:
        unreal_boundary = UnrealBoundary()
        requested_exclusive_end = 101

        grandchild_camera_cut = FakeMovieSceneSubSection(12, 70)
        grandchild = FakeLevelSequence(
            12,
            70,
            path_name=f"{UnrealBoundary.CHILD_PATH}_Nested",
            camera_cut_sections=[grandchild_camera_cut],
            playback_range_locked=True,
        )

        nested_section = FakeMovieSceneSubSection(12, 70, grandchild)
        nested_section.parameters.first_loop_start_frame_offset = 4
        child_camera_cut = FakeMovieSceneSubSection(8, 80)
        child = FakeLevelSequence(
            8,
            80,
            path_name=UnrealBoundary.CHILD_PATH,
            subsections=[nested_section],
            camera_cut_sections=[child_camera_cut],
            playback_range_locked=True,
        )
        unreal_boundary.child = child

        master_shot_section = FakeMovieSceneSubSection(5, 90, child)
        master_shot_section.parameters.start_frame_offset = 6
        unreal_boundary.master.shot_subsections = [master_shot_section]
        set_frame_range = load_set_frame_range(unreal_boundary)

        result = set_frame_range.run(
            "S3Bishop",
            "TIC",
            "TIC_000_0450",
            0,
            100,
        )

        self.assertTrue(result)
        for sequence in (child, grandchild):
            self.assertEqual(0, sequence.start_frame)
            self.assertEqual(requested_exclusive_end, sequence.exclusive_end_frame)
            self.assertFalse(sequence.playback_range_locked)

        for section in (
            master_shot_section,
            nested_section,
            child_camera_cut,
            grandchild_camera_cut,
        ):
            self.assertEqual(0, section.start_frame)
            self.assertEqual(requested_exclusive_end, section.exclusive_end_frame)

        self.assertEqual(0, master_shot_section.parameters.start_frame_offset)
        self.assertEqual(0, nested_section.parameters.first_loop_start_frame_offset)
        self.assertCountEqual(
            [unreal_boundary.master, child, grandchild],
            unreal_boundary.saved_assets,
        )
        self.assertNotIn(unreal_boundary.data_asset, unreal_boundary.saved_assets)


if __name__ == "__main__":
    unittest.main()
