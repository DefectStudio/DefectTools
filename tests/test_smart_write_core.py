from __future__ import annotations

import sys
from pathlib import Path


PLUGIN_DIR = Path(__file__).resolve().parents[1] / "natron_plugins"
sys.path.insert(0, str(PLUGIN_DIR))

from smart_write_core import (  # noqa: E402
    build_output_paths,
    existing_output_versions,
    next_output_version,
)


def test_build_output_paths_matches_pipeline_layout() -> None:
    project_directory = Path(
        "F:/Defect Dropbox/defect/s3bishop/sequences/BSH/"
        "BSH_000_0020/comp/natron"
    )

    paths = build_output_paths(project_directory, version=1)

    base = (
        "F:/Defect Dropbox/defect/s3bishop/sequences/BSH/"
        "BSH_000_0020/comp/_output"
    )
    assert paths.exr_sequence.as_posix() == (
        base
        + "/BSH_000_0020_beauty_v001/"
        "BSH_000_0020_beauty_v001.####.exr"
    )
    assert paths.mp4_file.as_posix() == base + "/BSH_000_0020_beauty_v001.mp4"
    assert paths.mov_file.as_posix() == base + "/BSH_000_0020_beauty_v001.mov"
    assert paths.hero_sequence.as_posix() == (
        base + "/_hero/BSH_000_0020.####.exr"
    )


def test_versioned_outputs_share_the_next_highest_version(tmp_path: Path) -> None:
    shot_root = tmp_path / "sequences" / "BSH" / "BSH_000_0020"
    project_directory = shot_root / "comp" / "natron"
    output_directory = shot_root / "comp" / "_output"
    project_directory.mkdir(parents=True)
    output_directory.mkdir(parents=True)

    (output_directory / "BSH_000_0020_beauty_v001").mkdir()
    (output_directory / "BSH_000_0020_beauty_v003.mp4").touch()
    (output_directory / "BSH_000_0020_beauty_v007.mov").touch()
    (output_directory / "_hero").mkdir()
    (output_directory / "BSH_000_0020_environment_v099").mkdir()

    assert existing_output_versions(project_directory) == (1, 3, 7)
    assert next_output_version(project_directory) == 8

    paths = build_output_paths(project_directory)

    assert paths.version == 8
    assert "beauty_v008" in paths.exr_sequence.as_posix()
    assert paths.mp4_file.name == "BSH_000_0020_beauty_v008.mp4"
    assert paths.mov_file.name == "BSH_000_0020_beauty_v008.mov"
    assert paths.hero_sequence.name == "BSH_000_0020.####.exr"


def test_build_output_paths_requires_comp_natron_project_location() -> None:
    try:
        build_output_paths(Path("F:/show/BSH_000_0020"))
    except ValueError as error:
        assert "comp/natron" in str(error).replace("\\", "/")
    else:
        raise AssertionError("Expected invalid project layout to be rejected")
