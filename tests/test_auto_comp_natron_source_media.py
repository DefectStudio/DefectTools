from __future__ import annotations

from pathlib import Path

import pytest

from portable_pipe_tools.auto_comp_natron import source_media


def _create_source_version(
    show_root: Path,
    version: int,
    frames: tuple[int, ...],
) -> Path:
    shot_name = "BSH_000_0020"
    version_name = f"{shot_name}_beauty_v{version:03d}"
    version_directory = (
        show_root
        / "sequences"
        / "BSH"
        / shot_name
        / "lite"
        / "unreal"
        / "_output"
        / version_name
    )
    version_directory.mkdir(parents=True)
    for frame in frames:
        (version_directory / f"{version_name}.{frame}.exr").write_bytes(b"exr")
    return version_directory


def test_find_latest_source_sequence_uses_latest_beauty_version(tmp_path) -> None:
    show_root = tmp_path / "show"
    _create_source_version(show_root, 1, (1001, 1002))
    latest = _create_source_version(show_root, 12, (1050, 1052, 1051))

    directory, source_files = source_media.find_latest_source_sequence(
        show_root,
        "BSH",
        "BSH_000_0020",
    )

    assert directory == latest
    assert [path.name for path in source_files] == [
        "BSH_000_0020_beauty_v012.1050.exr",
        "BSH_000_0020_beauty_v012.1051.exr",
        "BSH_000_0020_beauty_v012.1052.exr",
    ]


def test_hydrate_latest_source_sequence_downloads_only_placeholders(
    tmp_path,
    monkeypatch,
) -> None:
    show_root = tmp_path / "show"
    _create_source_version(show_root, 2, (1001, 1002, 1003))
    hydrated = []
    monkeypatch.setattr(
        source_media,
        "_needs_hydration",
        lambda path: path.name.endswith(("1001.exr", "1003.exr")),
    )
    monkeypatch.setattr(
        source_media,
        "_hydrate_placeholder",
        hydrated.append,
    )
    progress = []

    result = source_media.hydrate_latest_source_sequence(
        show_root,
        "BSH",
        "BSH_000_0020",
        progress=lambda completed, total, path: progress.append(
            (completed, total, path.name)
        ),
    )

    assert result.source_files == 3
    assert result.hydrated_files == 2
    assert [path.name for path in hydrated] == [
        "BSH_000_0020_beauty_v002.1001.exr",
        "BSH_000_0020_beauty_v002.1003.exr",
    ]
    assert progress == [
        (0, 2, "BSH_000_0020_beauty_v002.1001.exr"),
        (1, 2, "BSH_000_0020_beauty_v002.1001.exr"),
        (2, 2, "BSH_000_0020_beauty_v002.1003.exr"),
    ]


def test_hydrate_placeholder_reports_source_path(tmp_path, monkeypatch) -> None:
    source_path = tmp_path / "frame.exr"
    source_path.touch()

    def fail_open(*_args, **_kwargs):
        raise OSError("Dropbox is unavailable")

    monkeypatch.setattr(Path, "open", fail_open)

    with pytest.raises(source_media.SourceHydrationError) as error:
        source_media._hydrate_placeholder(source_path)

    assert error.value.source_path == source_path
    assert "Dropbox is unavailable" in str(error.value)
