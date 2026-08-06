from pathlib import Path
import sys


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "natron_plugins"
sys.path.insert(0, str(PLUGIN_DIR))
try:
    from smart_read_core import (
        find_exr_versions,
        latest_exr_version,
        project_directory_from_paths,
        shot_root_from_project_directory,
    )
finally:
    sys.path.remove(str(PLUGIN_DIR))


def _make_exr_version(
    shot_root: Path,
    version: int,
    frames: range,
    element: str = "beauty",
) -> Path:
    name = f"{shot_root.name}_{element}_v{version:03d}"
    directory = shot_root / "lite" / "unreal" / "_output" / name
    directory.mkdir(parents=True)
    for frame in frames:
        (directory / f"{name}.{frame:04d}.exr").touch()
    return directory


def test_project_directory_is_read_from_natron_project_paths():
    result = project_directory_from_paths(
        [["OCIO", "C:/ocio"], ["Project", "F:/repo/show/shot/comp/natron"]]
    )

    assert result == Path("F:/repo/show/shot/comp/natron")


def test_shot_root_requires_comp_natron_layout(tmp_path):
    project_directory = tmp_path / "SHOT_000_0010" / "comp" / "natron"

    assert shot_root_from_project_directory(project_directory) == project_directory.parent.parent


def test_exr_versions_are_scanned_relative_to_project_and_sorted(tmp_path):
    shot_root = tmp_path / "SHOT_000_0010"
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    _make_exr_version(shot_root, 1, range(1001, 1004))
    latest_directory = _make_exr_version(shot_root, 28, range(1001, 1006))

    mp4_only = shot_root / "lite" / "unreal" / "_output" / f"{shot_root.name}_beauty_v029"
    mp4_only.mkdir()
    (mp4_only / f"{shot_root.name}_beauty_v029.mp4").touch()

    versions = find_exr_versions(project_directory)

    assert [item.label for item in versions] == ["v001", "v028"]
    assert latest_exr_version(versions) == versions[-1]
    assert versions[-1].directory == latest_directory
    assert versions[-1].sequence_path.name == "SHOT_000_0010_beauty_v028.####.exr"
    assert (versions[-1].first_frame, versions[-1].last_frame) == (1001, 1005)


def test_exr_versions_are_filtered_by_element(tmp_path):
    shot_root = tmp_path / "SHOT_000_0010"
    project_directory = shot_root / "comp" / "natron"
    project_directory.mkdir(parents=True)
    _make_exr_version(shot_root, 5, range(1001, 1003), element="beauty")
    environment = _make_exr_version(
        shot_root,
        2,
        range(1010, 1013),
        element="environment",
    )

    versions = find_exr_versions(project_directory, "Environment")

    assert [item.label for item in versions] == ["v002"]
    assert versions[0].directory == environment
    assert versions[0].first_frame == 1010
