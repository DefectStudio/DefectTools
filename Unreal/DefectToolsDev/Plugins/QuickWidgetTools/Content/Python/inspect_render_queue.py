"""Read-only Movie Render Queue inspector for the Render Farm bridge.

This module is intended for an Editor Utility Widget ``Execute Python Script``
node. It inspects the current Movie Render Queue without allocating, deleting,
reordering, consuming, enabling, disabling, or otherwise editing queue jobs.

Blueprint usage::

    import inspect_render_queue
    import importlib
    importlib.reload(inspect_render_queue)

    result_summary = inspect_render_queue.run()

The complete preview is written to::

    <Project>/Saved/RenderFarm/Preview/render_queue_preview.json

``run()`` returns a compact semicolon-delimited summary that is friendly to an
Execute Python Script node output pin. The JSON preview is deliberately not a
production farm job yet; it lets us confirm what Unreal 5.8 exposes before the
publisher contract is locked down.
"""

from __future__ import annotations

from datetime import datetime, timezone
import getpass
import json
import os
import socket
import traceback
from typing import Any
from uuid import uuid4

import unreal


LOG_PREFIX = "[InspectRenderQueue]"
PREVIEW_SCHEMA_VERSION = 1
DEFAULT_PREVIEW_FILE_NAME = "render_queue_preview.json"


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message: str) -> None:
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _enum_text(value: Any) -> str:
    if value is None:
        return ""

    enum_name = getattr(value, "name", None)
    if enum_name:
        return _safe_text(enum_name).strip().lower()

    text = _safe_text(value).strip().strip("<>")
    if not text:
        return ""

    # Unreal enum strings commonly look like either:
    #   MoviePipelineConfigMode.GRAPH
    #   <MoviePipelineConfigMode.GRAPH: 1>
    # Keep only the symbolic member name.
    enum_member = text.rsplit(".", 1)[-1]
    enum_member = enum_member.split(":", 1)[0]
    return enum_member.strip().lower()


def _call(obj: Any, method_name: str, *args: Any, default: Any = None) -> Any:
    if obj is None:
        return default
    method = getattr(obj, method_name, None)
    if not callable(method):
        return default
    try:
        return method(*args)
    except Exception:
        return default


def _editor_property(obj: Any, *property_names: str, default: Any = None) -> Any:
    if obj is None:
        return default

    getter = getattr(obj, "get_editor_property", None)
    for property_name in property_names:
        if callable(getter):
            try:
                return getter(property_name)
            except Exception:
                pass
        try:
            return getattr(obj, property_name)
        except Exception:
            pass

    return default


def _object_path(value: Any) -> str:
    """Return a stable Unreal object/soft-object path when one is available."""
    if value is None:
        return ""

    for method_name in (
        "get_path_name",
        "get_asset_path_name",
        "to_string",
        "export_text",
    ):
        text = _call(value, method_name, default="")
        if text:
            normalized = _safe_text(text).strip().strip("\"'")
            if normalized.startswith("SoftObjectPath(") and normalized.endswith(")"):
                normalized = normalized[len("SoftObjectPath(") : -1].strip().strip("\"'")
            if normalized:
                return normalized

    text = _safe_text(value).strip()
    if text.startswith("SoftObjectPath(") and text.endswith(")"):
        text = text[len("SoftObjectPath(") : -1].strip().strip("\"'")
    if text in {"None", "NoneType", "<Object '/Script/CoreUObject.None'>"}:
        return ""
    return text


def _class_name(value: Any) -> str:
    class_object = _call(value, "get_class")
    name = _call(class_object, "get_name", default="")
    return _safe_text(name) or type(value).__name__


def _struct_or_value(value: Any) -> Any:
    """Convert common Unreal values to JSON-safe diagnostic data."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, dict):
        return {str(key): _struct_or_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_struct_or_value(item) for item in value]

    path_value = _editor_property(value, "path", default=None)
    if path_value is not None:
        return {"path": _safe_text(path_value)}

    exported = _call(value, "export_text", default="")
    if exported:
        return _safe_text(exported)

    object_path = _object_path(value)
    return object_path or _safe_text(value)


def _frame_rate_data(frame_rate: Any) -> dict[str, int] | None:
    if frame_rate is None:
        return None

    numerator = _editor_property(frame_rate, "numerator", default=None)
    denominator = _editor_property(frame_rate, "denominator", default=None)
    try:
        numerator = int(numerator)
        denominator = int(denominator)
    except (TypeError, ValueError):
        return None

    return {"numerator": numerator, "denominator": denominator}


def _frame_rate_components(frame_rate: Any) -> tuple[int, int]:
    data = _frame_rate_data(frame_rate)
    if data is None:
        raise ValueError(f"Invalid frame rate: {_safe_text(frame_rate)}")

    numerator = data["numerator"]
    denominator = data["denominator"]
    if numerator <= 0 or denominator <= 0:
        raise ValueError(
            f"Frame rate numerator and denominator must be positive: {data}"
        )
    return numerator, denominator


def _frame_number_value(value: Any) -> int:
    raw_value = _editor_property(value, "value", default=value)
    return int(raw_value)


def _transform_frame_number(
    frame_number: Any,
    source_rate: Any,
    destination_rate: Any,
    rounding: str,
) -> int:
    """Transform a frame number between rates using exact integer arithmetic."""
    source_numerator, source_denominator = _frame_rate_components(source_rate)
    destination_numerator, destination_denominator = _frame_rate_components(
        destination_rate
    )

    # destination_frames = source_frames * destination_fps / source_fps
    scaled_numerator = (
        int(frame_number) * destination_numerator * source_denominator
    )
    scaled_denominator = destination_denominator * source_numerator

    if rounding == "floor":
        return scaled_numerator // scaled_denominator
    if rounding == "ceil":
        return -(-scaled_numerator // scaled_denominator)
    raise ValueError(f"Unsupported frame conversion rounding mode: {rounding}")


def _to_tick_resolution_frame(
    level_sequence: Any,
    frame_number: Any,
    rounding: str,
) -> int:
    display_rate = level_sequence.get_display_rate()
    tick_resolution = level_sequence.get_tick_resolution()
    return _transform_frame_number(
        frame_number=frame_number,
        source_rate=display_rate,
        destination_rate=tick_resolution,
        rounding=rounding,
    )


def _load_asset_from_object_path(object_path: str) -> Any:
    path = _safe_text(object_path).strip()
    if not path:
        return None
    try:
        return unreal.load_asset(path)
    except Exception:
        return None


def _inspect_sequence_playback_range(
    sequence_object_path: str,
    warnings: list[str],
) -> dict[str, Any] | None:
    sequence = _load_asset_from_object_path(sequence_object_path)
    if sequence is None:
        warnings.append(f"Could not load sequence asset: {sequence_object_path}")
        return None

    level_sequence_class = getattr(unreal, "LevelSequence", None)
    if level_sequence_class is not None and not isinstance(sequence, level_sequence_class):
        warnings.append(
            f"Sequence path did not load a LevelSequence: {sequence_object_path} "
            f"(class={_class_name(sequence)})"
        )
        return None

    try:
        # In Unreal Python, LevelSequence.get_playback_start/end() return
        # display-rate frame numbers even though the underlying MovieScene range
        # is stored at tick resolution. The upper bound remains exclusive.
        playback_start_display = _frame_number_value(sequence.get_playback_start())
        playback_end_display_exclusive = _frame_number_value(
            sequence.get_playback_end()
        )
        playback_start_tick = _to_tick_resolution_frame(
            sequence,
            playback_start_display,
            rounding="floor",
        )
        playback_end_tick_exclusive = _to_tick_resolution_frame(
            sequence,
            playback_end_display_exclusive,
            rounding="ceil",
        )

        display_frame_count = max(
            0,
            playback_end_display_exclusive - playback_start_display,
        )
        playback_end_display_inclusive = (
            playback_end_display_exclusive - 1
            if display_frame_count > 0
            else playback_start_display
        )

        return {
            "source": "level_sequence_playback_range",
            "tick_resolution": _frame_rate_data(sequence.get_tick_resolution()),
            "display_rate": _frame_rate_data(sequence.get_display_rate()),
            "display_start": playback_start_display,
            "display_end_exclusive": playback_end_display_exclusive,
            "display_end_inclusive": playback_end_display_inclusive,
            "display_frame_count": display_frame_count,
            "tick_start": playback_start_tick,
            "tick_end_exclusive": playback_end_tick_exclusive,
            "note": (
                "Unreal Python reports Level Sequence playback bounds in display "
                "frames, with an exclusive upper bound. The farm-facing inclusive "
                "end is display_end_exclusive - 1. Tick values are calculated only "
                "for comparison with Movie Render Pipeline logs. An active MRQ/MRG "
                "custom range can override this sequence fallback."
            ),
        }
    except Exception as exc:
        warnings.append(
            f"Could not inspect sequence playback range for {sequence_object_path}: {exc}"
        )
        return None


def _out_bool(value: Any) -> bool | None:
    """Normalize Unreal functions that return (success, out_value)."""
    if isinstance(value, tuple):
        if len(value) >= 2 and isinstance(value[0], bool):
            return bool(value[1]) if value[0] else None
        if value:
            return bool(value[-1])
        return None
    if isinstance(value, bool):
        return value
    return None


def _graph_from_assignment_container(container: Any) -> tuple[Any, str]:
    graph_reference = _call(container, "get_graph_config")
    graph_path = _object_path(graph_reference)

    graph = graph_reference
    if graph_reference is not None and not callable(getattr(graph_reference, "get_variables", None)):
        graph = _call(graph_reference, "load_synchronous")
    if graph is None or not callable(getattr(graph, "get_variables", None)):
        graph = _load_asset_from_object_path(graph_path)

    return graph, graph_path


def _inspect_graph_assignment_container(
    container: Any,
    container_index: int,
    warnings: list[str],
) -> dict[str, Any]:
    graph, graph_path = _graph_from_assignment_container(container)
    result: dict[str, Any] = {
        "index": container_index,
        "graph": graph_path,
        "variables": [],
    }

    if graph is None:
        warnings.append(
            f"Could not resolve graph for variable-assignment container {container_index}."
        )
        return result

    variables = _call(graph, "get_variables", default=[])
    try:
        variables = list(variables or [])
    except TypeError:
        variables = []

    for variable in variables:
        variable_name = _call(variable, "get_member_name", default="")
        variable_name = _safe_text(variable_name) or _call(
            variable,
            "get_name",
            default="",
        )

        enabled_raw = _call(
            container,
            "get_variable_assignment_enable_state",
            variable,
            default=None,
        )
        value_type = _call(container, "get_value_type", variable, default=None)
        container_type = _call(
            container,
            "get_value_container_type",
            variable,
            default=None,
        )
        value_type_object = _call(
            container,
            "get_value_type_object",
            variable,
            default=None,
        )
        serialized_value = _call(
            container,
            "get_value_serialized_string",
            variable,
            default="",
        )

        result["variables"].append(
            {
                "name": _safe_text(variable_name),
                "enabled": _out_bool(enabled_raw),
                "value_type": _enum_text(value_type),
                "container_type": _enum_text(container_type),
                "value_type_object": _object_path(value_type_object),
                "serialized_value": _safe_text(serialized_value),
            }
        )

    return result


def _inspect_graph_assignments(
    owner: Any,
    property_names: tuple[str, ...],
    owner_label: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    containers = _editor_property(owner, *property_names, default=[])
    try:
        containers = list(containers or [])
    except TypeError:
        warnings.append(f"{owner_label} graph variable assignments were not iterable.")
        return []

    results = []
    for index, container in enumerate(containers):
        try:
            results.append(
                _inspect_graph_assignment_container(container, index, warnings)
            )
        except Exception as exc:
            warnings.append(
                f"Could not inspect {owner_label} graph assignment {index}: {exc}"
            )
    return results


def _inspect_console_variable_overrides(owner: Any) -> list[dict[str, Any]]:
    entries = _editor_property(owner, "console_variable_overrides", default=[])
    try:
        entries = list(entries or [])
    except TypeError:
        return []

    result = []
    for entry in entries:
        result.append(
            {
                "name": _safe_text(
                    _editor_property(entry, "name", default="")
                ),
                "value": _struct_or_value(
                    _editor_property(entry, "value", default=None)
                ),
                "enabled": bool(
                    _editor_property(
                        entry,
                        "is_enabled",
                        "enabled",
                        default=True,
                    )
                ),
            }
        )
    return result


def _inspect_legacy_output_setting(job: Any, warnings: list[str]) -> dict[str, Any] | None:
    configuration = _call(job, "get_configuration")
    output_setting_class = getattr(unreal, "MoviePipelineOutputSetting", None)
    if configuration is None or output_setting_class is None:
        return None

    output_setting = _call(
        configuration,
        "find_setting_by_class",
        output_setting_class,
    )
    if output_setting is None:
        return None

    properties = (
        "output_directory",
        "file_name_format",
        "output_resolution",
        "use_custom_playback_range",
        "custom_start_frame",
        "custom_end_frame",
        "zero_pad_frame_numbers",
        "frame_number_offset",
        "output_frame_step",
        "flush_disk_writes_per_shot",
    )
    result = {
        property_name: _struct_or_value(
            _editor_property(output_setting, property_name, default=None)
        )
        for property_name in properties
    }

    if result.get("use_custom_playback_range"):
        warnings.append(
            "Legacy MRQ custom playback range is enabled; its raw start/end values "
            "are included and take precedence over the sequence fallback."
        )

    return result


def _inspect_basic_config(job: Any, warnings: list[str]) -> dict[str, Any] | None:
    basic_config = _call(job, "get_basic_config")
    if basic_config is None:
        return None

    properties = (
        "output_directory",
        "file_name_format",
        "output_resolution",
        "enabled_output_types",
        "override_custom_start_frame",
        "override_custom_end_frame",
        "custom_start_frame",
        "custom_end_frame",
        "use_deferred_renderer",
        "deferred_spatial_sample_count",
        "use_path_traced_renderer",
        "path_traced_spatial_sample_count",
        "num_warm_up_frames",
        "temporal_sample_count",
    )
    result = {
        property_name: _struct_or_value(
            _editor_property(basic_config, property_name, default=None)
        )
        for property_name in properties
    }

    if result.get("override_custom_start_frame") or result.get(
        "override_custom_end_frame"
    ):
        warnings.append(
            "Basic configuration frame overrides are active; raw override values "
            "are included and take precedence over the sequence fallback."
        )

    return result


def _inspect_shot(shot: Any, shot_index: int, job_label: str) -> dict[str, Any]:
    warnings: list[str] = []
    graph_preset = _call(shot, "get_graph_preset")
    shot_override_configuration = _call(shot, "get_shot_override_configuration")
    shot_override_preset_origin = _call(shot, "get_shot_override_preset_origin")

    enabled = _call(shot, "should_render", default=None)
    if enabled is None:
        enabled = _editor_property(shot, "enabled", default=True)

    result = {
        "index": shot_index,
        "enabled": bool(enabled),
        "outer_name": _safe_text(
            _editor_property(shot, "outer_name", default="")
        ),
        "inner_name": _safe_text(
            _editor_property(shot, "inner_name", default="")
        ),
        "graph_preset": _object_path(graph_preset),
        "shot_override_configuration": _object_path(shot_override_configuration),
        "shot_override_preset_origin": _object_path(shot_override_preset_origin),
        "console_variable_overrides": _inspect_console_variable_overrides(shot),
        "graph_variable_assignments": _inspect_graph_assignments(
            shot,
            ("graph_variable_assignments",),
            f"{job_label} shot {shot_index}",
            warnings,
        ),
        "primary_graph_variable_assignments": _inspect_graph_assignments(
            shot,
            ("primary_graph_variable_assignments",),
            f"{job_label} shot {shot_index} primary",
            warnings,
        ),
        "warnings": warnings,
    }
    return result


def _inspect_job(job: Any, job_index: int) -> dict[str, Any]:
    warnings: list[str] = []
    job_name = _safe_text(_editor_property(job, "job_name", default=""))
    job_label = job_name or f"Job {job_index}"

    sequence_path = _object_path(_editor_property(job, "sequence", default=None))
    map_path = _object_path(_editor_property(job, "map", default=None))

    graph_preset = _call(job, "get_graph_preset")
    preset_origin = _call(job, "get_preset_origin")
    configuration = _call(job, "get_configuration")
    config_mode = _call(job, "get_config_mode", default=None)

    shots = _editor_property(job, "shot_info", default=[])
    try:
        shots = list(shots or [])
    except TypeError:
        shots = []
        warnings.append("shot_info was not iterable.")

    result = {
        "queue_index": job_index,
        "job_name": job_name,
        "enabled": bool(_call(job, "is_enabled", default=True)),
        "consumed": bool(_call(job, "is_consumed", default=False)),
        "author": _safe_text(_editor_property(job, "author", default="")),
        "comment": _safe_text(_editor_property(job, "comment", default="")),
        "user_data": _safe_text(_editor_property(job, "user_data", default="")),
        "status_message": _safe_text(
            _call(job, "get_status_message", default="")
        ),
        "status_progress": _call(job, "get_status_progress", default=None),
        "map": map_path,
        "sequence": sequence_path,
        "config_mode": _enum_text(config_mode),
        "is_using_graph_configuration": bool(
            _call(job, "is_using_graph_configuration", default=False)
        ),
        "is_using_basic_configuration": bool(
            _call(job, "is_using_basic_configuration", default=False)
        ),
        "graph_preset": _object_path(graph_preset),
        "legacy_preset_origin": _object_path(preset_origin),
        "legacy_configuration": {
            "class": _class_name(configuration) if configuration else "",
            "object_path": _object_path(configuration),
        },
        "sequence_playback_range": _inspect_sequence_playback_range(
            sequence_path,
            warnings,
        ),
        "legacy_output_setting": _inspect_legacy_output_setting(job, warnings),
        "basic_config": _inspect_basic_config(job, warnings),
        "console_variable_overrides": _inspect_console_variable_overrides(job),
        "graph_variable_assignments": _inspect_graph_assignments(
            job,
            ("graph_variable_assignments",),
            job_label,
            warnings,
        ),
        "shots": [
            _inspect_shot(shot, shot_index, job_label)
            for shot_index, shot in enumerate(shots)
        ],
        "warnings": warnings,
    }

    return result


def _project_file_path() -> str:
    path_getter = getattr(unreal.Paths, "get_project_file_path", None)
    project_file = ""
    if callable(path_getter):
        try:
            project_file = _safe_text(path_getter())
        except Exception:
            project_file = ""

    if project_file and not os.path.isabs(project_file):
        project_file = os.path.join(_safe_text(unreal.Paths.project_dir()), project_file)
    return os.path.normpath(project_file) if project_file else ""


def _engine_version() -> str:
    system_library = getattr(unreal, "SystemLibrary", None)
    version = _call(system_library, "get_engine_version", default="")
    return _safe_text(version)


def inspect_queue() -> dict[str, Any]:
    """Return a JSON-safe snapshot of the current editor Movie Render Queue."""
    queue_subsystem = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    if queue_subsystem is None:
        raise RuntimeError("Could not get MoviePipelineQueueSubsystem.")

    queue = queue_subsystem.get_queue()
    if queue is None:
        raise RuntimeError("MoviePipelineQueueSubsystem did not return a queue.")

    jobs = list(queue.get_jobs() or [])
    inspected_jobs = []
    document_warnings: list[str] = []

    for job_index, job in enumerate(jobs):
        try:
            inspected_jobs.append(_inspect_job(job, job_index))
        except Exception as exc:
            job_name = _safe_text(_editor_property(job, "job_name", default=""))
            warning = (
                f"Could not completely inspect job {job_index} "
                f"('{job_name}'): {type(exc).__name__}: {exc}"
            )
            document_warnings.append(warning)
            inspected_jobs.append(
                {
                    "queue_index": job_index,
                    "job_name": job_name,
                    "inspection_error": warning,
                }
            )

    queue_origin = _call(queue, "get_queue_origin")
    queue_dirty = _call(queue, "is_dirty", default=None)

    project_file = _project_file_path()

    return {
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
        "preview_only": True,
        "generated_utc": _utc_now(),
        "source": {
            "project_name": os.path.splitext(os.path.basename(project_file))[0],
            "project_file": project_file,
            "project_dir": os.path.normpath(_safe_text(unreal.Paths.project_dir())),
            "engine_version": _engine_version(),
            "computer": _safe_text(
                os.environ.get("COMPUTERNAME") or socket.gethostname()
            ),
            "user": _safe_text(getpass.getuser()),
        },
        "queue": {
            "object_path": _object_path(queue),
            "origin": _object_path(queue_origin),
            "is_dirty": queue_dirty,
            "job_count": len(inspected_jobs),
            "jobs": inspected_jobs,
        },
        "warnings": document_warnings,
    }


def _default_preview_path() -> str:
    saved_dir_getter = getattr(unreal.Paths, "project_saved_dir", None)
    saved_dir = ""
    if callable(saved_dir_getter):
        try:
            saved_dir = _safe_text(saved_dir_getter())
        except Exception:
            saved_dir = ""

    if not saved_dir:
        saved_dir = os.path.join(_safe_text(unreal.Paths.project_dir()), "Saved")

    return os.path.normpath(
        os.path.join(
            saved_dir,
            "RenderFarm",
            "Preview",
            DEFAULT_PREVIEW_FILE_NAME,
        )
    )


def _normalize_preview_path(preview_output_path: str | None) -> str:
    path = _safe_text(preview_output_path).strip()
    if not path:
        return _default_preview_path()

    path = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(path):
        path = os.path.join(_safe_text(unreal.Paths.project_dir()), path)
    if not path.lower().endswith(".json"):
        path = os.path.join(path, DEFAULT_PREVIEW_FILE_NAME)
    return os.path.normpath(path)


def _write_json_atomic(path: str, data: dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary_path = os.path.join(
        directory,
        f".{os.path.basename(path)}.{uuid4().hex}.tmp",
    )

    try:
        with open(temporary_path, "x", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=4, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
        except OSError:
            pass


def _count_warnings(document: dict[str, Any]) -> int:
    count = len(document.get("warnings", []))
    for job in document.get("queue", {}).get("jobs", []):
        count += len(job.get("warnings", []))
        for shot in job.get("shots", []):
            count += len(shot.get("warnings", []))
    return count


def _format_summary(
    success: bool,
    jobs_found: int = 0,
    enabled_jobs: int = 0,
    disabled_jobs: int = 0,
    consumed_jobs: int = 0,
    warnings: int = 0,
    preview_file: str = "",
    message: str = "",
) -> str:
    clean_message = _safe_text(message).replace(";", ",").replace("\n", " ")
    return (
        f"success={1 if success else 0};"
        f"jobs_found={jobs_found};"
        f"enabled_jobs={enabled_jobs};"
        f"disabled_jobs={disabled_jobs};"
        f"consumed_jobs={consumed_jobs};"
        f"warnings={warnings};"
        f"preview_file={preview_file};"
        f"message={clean_message}"
    )


def run(preview_output_path: str = "") -> str:
    """Inspect MRQ, save a preview JSON, and return a Blueprint-friendly summary."""
    try:
        _log("Starting read-only Movie Render Queue inspection...")
        document = inspect_queue()
        preview_path = _normalize_preview_path(preview_output_path)
        _write_json_atomic(preview_path, document)

        jobs = document["queue"]["jobs"]
        enabled_jobs = sum(1 for job in jobs if job.get("enabled", False))
        disabled_jobs = sum(1 for job in jobs if not job.get("enabled", False))
        consumed_jobs = sum(1 for job in jobs if job.get("consumed", False))
        warning_count = _count_warnings(document)

        for job in jobs:
            _log(
                "Job {index}: name='{name}', enabled={enabled}, consumed={consumed}, "
                "mode='{mode}', map='{map_path}', sequence='{sequence_path}', "
                "graph='{graph}'".format(
                    index=job.get("queue_index", "?"),
                    name=job.get("job_name", ""),
                    enabled=job.get("enabled", "unknown"),
                    consumed=job.get("consumed", "unknown"),
                    mode=job.get("config_mode", ""),
                    map_path=job.get("map", ""),
                    sequence_path=job.get("sequence", ""),
                    graph=job.get("graph_preset", ""),
                )
            )

        _log(f"Read-only inspection complete. Jobs found: {len(jobs)}")
        _log(f"Preview JSON: {preview_path}")
        if warning_count:
            _log_warning(
                f"Inspection completed with {warning_count} warning(s). "
                "Review the JSON before defining the production job schema."
            )

        return _format_summary(
            success=True,
            jobs_found=len(jobs),
            enabled_jobs=enabled_jobs,
            disabled_jobs=disabled_jobs,
            consumed_jobs=consumed_jobs,
            warnings=warning_count,
            preview_file=preview_path,
            message="Read-only MRQ inspection completed.",
        )

    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        _log_error(message)
        _log_error(traceback.format_exc())
        return _format_summary(success=False, message=message)


if __name__ == "__main__":
    run()
