from __future__ import annotations

from dataclasses import dataclass
import ntpath
import os
from pathlib import Path, PureWindowsPath
from typing import Any

from portable_pipe_tools.render_farm.queue import (
    create_directory_with_retry,
    path_exists_with_retry,
    retry_transient_windows_lock,
)


@dataclass(frozen=True)
class WorkerOutputMapping:
    render_farm_root: Path
    submitted_output_directory: str
    local_show_file_server_path: Path
    output_relative_directory: str
    worker_output_directory: Path


def _absolute_path(value: str | Path) -> Path:
    return Path(os.path.abspath(Path(value).expanduser()))


def derive_show_file_server_path(render_farm_root: str | Path) -> Path:
    farm_root = _absolute_path(render_farm_root)
    if farm_root.name.casefold() != "renderfarm":
        raise ValueError(
            "The Show Render Farm Base Folder must be the folder named "
            f"'renderFarm': {farm_root}"
        )
    if not path_exists_with_retry(farm_root):
        raise FileNotFoundError(
            f"The Show Render Farm Base Folder does not exist: {farm_root}"
        )
    is_directory = retry_transient_windows_lock(
        farm_root.is_dir,
        description=f"Check Render Farm Base Folder {farm_root}",
    )
    if not is_directory:
        raise NotADirectoryError(
            f"The Show Render Farm Base Folder is not a folder: {farm_root}"
        )
    return farm_root.parent


def _validated_relative_parts(value: str) -> tuple[str, ...]:
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        raise ValueError("The farm job has an empty output-relative directory.")
    if normalized.startswith("/") or ntpath.isabs(normalized):
        raise ValueError(
            f"The farm job output-relative directory must be relative: {value!r}"
        )

    parts = tuple(part for part in normalized.split("/") if part not in ("", "."))
    if not parts or any(part == ".." for part in parts):
        raise ValueError(
            "The farm job output-relative directory escapes the show folder: "
            f"{value!r}"
        )
    return parts


def _relative_parts_from_submitted_paths(job: dict[str, Any]) -> tuple[str, ...]:
    submitted_output = str(
        job.get("submitted_output_directory")
        or job.get("output_directory")
        or ""
    ).strip()
    if not submitted_output:
        raise ValueError("The farm job has no submitted output directory.")

    submitted_show_root = str(
        job.get("submitted_show_file_server_path") or ""
    ).strip()
    if submitted_show_root:
        try:
            relative = ntpath.relpath(submitted_output, submitted_show_root)
        except ValueError as error:
            raise ValueError(
                "The submitted output directory is not on the submitted show "
                "file-server path."
            ) from error
        return _validated_relative_parts(relative)

    # Backward compatibility for jobs published before the explicit relative
    # path fields existed. The project directory is the show root in this farm.
    project_name = str(job.get("project") or "").strip()
    if project_name:
        submitted_parts = PureWindowsPath(submitted_output).parts
        matching_indices = [
            index
            for index, part in enumerate(submitted_parts)
            if part.casefold() == project_name.casefold()
        ]
        if matching_indices:
            relative_parts = submitted_parts[matching_indices[-1] + 1 :]
            return _validated_relative_parts("/".join(relative_parts))

    raise ValueError(
        "This farm job does not contain a portable output-relative directory, "
        "and the worker could not infer one from its submitted output path. "
        "Republish the job with the updated Unreal farm publisher."
    )


def output_relative_parts(job: dict[str, Any]) -> tuple[str, ...]:
    explicit_relative = str(job.get("output_relative_directory") or "").strip()
    if explicit_relative:
        return _validated_relative_parts(explicit_relative)
    return _relative_parts_from_submitted_paths(job)


def resolve_worker_output_directory(
    job: dict[str, Any],
    local_show_file_server_path: str | Path,
) -> tuple[Path, str]:
    show_root = _absolute_path(local_show_file_server_path)
    parts = output_relative_parts(job)
    output_directory = _absolute_path(show_root.joinpath(*parts))
    try:
        common_path = os.path.commonpath((str(show_root), str(output_directory)))
    except ValueError as error:
        raise ValueError(
            "The worker output directory is not on the local show drive."
        ) from error
    if os.path.normcase(common_path) != os.path.normcase(str(show_root)):
        raise ValueError(
            "The worker output directory escapes the local show file-server path: "
            f"{output_directory}"
        )
    return output_directory, "/".join(parts)


def _child_path(root: Path, portable_name: str) -> Path:
    parts = tuple(
        part
        for part in portable_name.replace("\\", "/").split("/")
        if part not in ("", ".")
    )
    if any(part == ".." for part in parts):
        raise ValueError(f"Output filename format escapes its output folder: {portable_name}")
    return root.joinpath(*parts)


def find_existing_output_targets(
    job: dict[str, Any],
    worker_output_directory: str | Path,
) -> list[Path]:
    output_root = _absolute_path(worker_output_directory)
    existing: list[Path] = []

    mp4_format = str(job.get("mp4_file_name_format") or "").strip()
    if mp4_format:
        mp4_path = _child_path(output_root, mp4_format)
        if mp4_path.suffix.casefold() != ".mp4":
            mp4_path = mp4_path.with_name(mp4_path.name + ".mp4")
        if path_exists_with_retry(mp4_path):
            existing.append(mp4_path)

    exr_format = str(job.get("output_file_name_format") or "").strip()
    if exr_format:
        exr_template = _child_path(output_root, exr_format)
        exr_folder = exr_template.parent
        # Standard farm EXRs live in a version folder. Do not treat the output
        # root itself as a collision target if a nonstandard flat format is used.
        if exr_folder != output_root and path_exists_with_retry(exr_folder):
            contents = retry_transient_windows_lock(
                lambda: list(exr_folder.iterdir()),
                description=f"Inspect existing render output {exr_folder}",
            )
            if contents:
                existing.append(exr_folder)

    return existing


def prepare_worker_output_mapping(
    job: dict[str, Any],
    render_farm_root: str | Path,
) -> WorkerOutputMapping:
    farm_root = _absolute_path(render_farm_root)
    local_show_root = derive_show_file_server_path(farm_root)
    worker_output, relative_directory = resolve_worker_output_directory(
        job,
        local_show_root,
    )

    submitted_output = str(
        job.get("submitted_output_directory")
        or job.get("output_directory")
        or ""
    )
    job["submitted_output_directory"] = submitted_output
    job["worker_show_file_server_path"] = str(local_show_root)
    job["output_relative_directory"] = relative_directory
    job["worker_output_directory"] = str(worker_output)
    job["output_directory"] = str(worker_output)

    existing_targets = find_existing_output_targets(job, worker_output)
    if existing_targets:
        shot = str(job.get("shot_name") or "Unknown shot")
        raw_version = job.get("render_version")
        try:
            version = f"v{int(raw_version):03d}"
        except (TypeError, ValueError):
            version = str(raw_version or "unknown version")
        target_list = ", ".join(str(path) for path in existing_targets)
        raise FileExistsError(
            f"Output already exists for {shot} {version}. Choose a new render "
            f"version before submitting again. Existing target(s): {target_list}"
        )

    create_directory_with_retry(worker_output, parents=True, exist_ok=True)
    return WorkerOutputMapping(
        render_farm_root=farm_root,
        submitted_output_directory=submitted_output,
        local_show_file_server_path=local_show_root,
        output_relative_directory=relative_directory,
        worker_output_directory=worker_output,
    )
