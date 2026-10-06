from datetime import datetime, timezone
import importlib
import json
import os

import unreal

import gather_all_shots_and_frame_ranges
import get_outputFolder
import get_sequences
import get_shot_activeState
import get_shot_shot_order_number
import get_showname

LOG_PREFIX = "[ExportSequencesManifest]"
SCHEMA_VERSION = "1.0.0"
SEQUENCE_MANIFEST_TYPE = "sequence_shots_manifest"
PIPELINE_TOOL = "QuickWidgetTools"
PIPELINE_SCRIPT = "export_sequences_manifest.py"
FAILED_SHOT_ORDER_NUMBER = -1
LEGACY_ALL_SEQUENCES_MANIFEST_FILENAME = "all_sequences_shots_manifest.json"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _normalize_path(path_value):
    value = str(path_value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    value = value.replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    return value.rstrip("/")


def _sanitize_name(value, label):
    cleaned = "".join(ch for ch in str(value or "").strip() if ch.isalnum() or ch == "_")
    if not cleaned:
        raise ValueError(f"Invalid {label}: value is empty after sanitizing. Raw value: {value!r}")
    return cleaned


def _coerce_int(value, label, shot_name):
    try:
        return int(str(value).strip())
    except Exception:
        raise ValueError(f"Invalid {label} for shot '{shot_name}': {value!r}")


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "active"):
        return True
    if text in ("0", "false", "no", "n", "inactive", ""):
        return False
    return bool(value)


def _reload_dependencies():
    importlib.reload(get_showname)
    importlib.reload(get_sequences)
    importlib.reload(gather_all_shots_and_frame_ranges)
    importlib.reload(get_shot_activeState)
    importlib.reload(get_shot_shot_order_number)
    importlib.reload(get_outputFolder)


def _get_active_show_name():
    show_name = str(get_showname.run() or "").strip()
    if not show_name:
        raise RuntimeError("Could not resolve show name from get_showname.run().")
    return _sanitize_name(show_name, "show_name")


def _get_sequence_names(show_name):
    raw_sequences = get_sequences.run(show_name) or []
    sequence_names = [
        _sanitize_name(raw_sequence, "sequence_name").upper()
        for raw_sequence in list(raw_sequences)
    ]
    sequence_names = sorted(set(sequence_names))
    if not sequence_names:
        _log_warning(f"No sequences found for show '{show_name}'.")
    return sequence_names


def _get_sequence_shot_arrays(show_name, sequence_name):
    result = gather_all_shots_and_frame_ranges.run(show_name, sequence_name)
    if not result:
        return [], [], [], [], 0
    shot_names, start_frames, end_frames, level_paths, has_any_shots = result
    shot_names = list(shot_names or [])
    start_frames = list(start_frames or [])
    end_frames = list(end_frames or [])
    level_paths = list(level_paths or [])
    has_any_shots = int(has_any_shots or 0)
    counts = {len(shot_names), len(start_frames), len(end_frames), len(level_paths)}
    if len(counts) != 1:
        raise ValueError(f"Shot/frame arrays are mismatched for sequence '{sequence_name}'.")
    return shot_names, start_frames, end_frames, level_paths, has_any_shots


def _get_shot_active_state(show_name, sequence_name, shot_name):
    try:
        return _coerce_bool(get_shot_activeState.run(show_name, sequence_name, shot_name))
    except Exception as exc:
        _log_warning(f"Failed to read active state for shot '{shot_name}'. Defaulting to inactive. Error: {exc}")
        return False


def _get_order(show_name, sequence_name, shot_name):
    try:
        return int(get_shot_shot_order_number.run(show_name, sequence_name, shot_name))
    except Exception as exc:
        _log_warning(f"Failed to read ShotOrderNumber for shot '{shot_name}'. Using {FAILED_SHOT_ORDER_NUMBER}. Error: {exc}")
        return FAILED_SHOT_ORDER_NUMBER


def _build_sequence_shots(show_name, sequence_name):
    shot_names, start_frames, end_frames, level_paths, has_any_shots = _get_sequence_shot_arrays(show_name, sequence_name)
    if not has_any_shots or not shot_names:
        return []
    shots = []
    for index, shot_name in enumerate(shot_names):
        clean_shot_name = _sanitize_name(shot_name, "shot_name")
        start_frame = _coerce_int(start_frames[index], "start_frame", clean_shot_name)
        end_frame = _coerce_int(end_frames[index], "end_frame", clean_shot_name)
        if end_frame < start_frame:
            raise ValueError(f"Shot '{clean_shot_name}' has end_frame {end_frame} before start_frame {start_frame}.")
        is_active = _get_shot_active_state(show_name, sequence_name, clean_shot_name)
        shots.append(
            {
                "order": _get_order(show_name, sequence_name, clean_shot_name),
                "show_name": show_name,
                "sequence_name": sequence_name,
                "shot_name": clean_shot_name,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "level_path": str(level_paths[index] or "").strip(),
                "is_active": is_active,
                "is_active_value": 1 if is_active else 0,
            }
        )
    return shots


def _build_sequence_manifest(show_name, sequence_name, sequences_root_path, sequence_output_path, shots, generated_utc):
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_type": SEQUENCE_MANIFEST_TYPE,
        "pipeline_tool": PIPELINE_TOOL,
        "pipeline_script": PIPELINE_SCRIPT,
        "generated_utc": generated_utc,
        "show_name": show_name,
        "sequence_name": sequence_name,
        "sequences_root_path": sequences_root_path,
        "sequence_output_path": sequence_output_path,
        "output_path": sequence_output_path,
        "shot_count": len(shots),
        "active_shot_count": sum(1 for shot in shots if shot["is_active"]),
        "inactive_shot_count": sum(1 for shot in shots if not shot["is_active"]),
        "shots": shots,
    }


def _get_sequence_output_path(sequences_root_path, sequence_name):
    return os.path.normpath(os.path.join(sequences_root_path, sequence_name))


def _get_sequence_manifest_path(sequences_root_path, sequence_name):
    filename = f"{sequence_name.lower()}_sequence_shots_manifest.json"
    return os.path.normpath(os.path.join(_get_sequence_output_path(sequences_root_path, sequence_name), filename))


def _get_legacy_all_sequences_manifest_path(sequences_root_path):
    return os.path.normpath(os.path.join(sequences_root_path, LEGACY_ALL_SEQUENCES_MANIFEST_FILENAME))


def _delete_legacy_all_sequences_manifest(sequences_root_path):
    legacy_manifest_path = _get_legacy_all_sequences_manifest_path(sequences_root_path)
    if not os.path.isfile(legacy_manifest_path):
        return False
    os.remove(legacy_manifest_path)
    _log(f"Deleted legacy all-sequences manifest: {legacy_manifest_path}")
    return True


def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as manifest_file:
        json.dump(data, manifest_file, indent=4, ensure_ascii=False)
        manifest_file.write("\n")
    _log(f"Wrote JSON: {path}")


def run():
    try:
        _reload_dependencies()
        show_name = _get_active_show_name()
        sequence_names = _get_sequence_names(show_name)
        sequences_root_path = _normalize_path(get_outputFolder.run())
        if not sequences_root_path:
            raise RuntimeError("Could not resolve OutputPath from QuickWidgetToolsSettings.ini.")
        generated_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        written_sequence_paths = []
        total_shot_count = 0
        _log(f"Exporting sequence manifests for show '{show_name}' to: {sequences_root_path}")
        for sequence_name in sequence_names:
            shots = _build_sequence_shots(show_name, sequence_name)
            total_shot_count += len(shots)
            sequence_output_path = _get_sequence_output_path(sequences_root_path, sequence_name)
            sequence_manifest = _build_sequence_manifest(show_name, sequence_name, sequences_root_path, sequence_output_path, shots, generated_utc)
            sequence_manifest_path = _get_sequence_manifest_path(sequences_root_path, sequence_name)
            _write_json(sequence_manifest_path, sequence_manifest)
            written_sequence_paths.append(sequence_manifest_path)
        try:
            _delete_legacy_all_sequences_manifest(sequences_root_path)
        except Exception as exc:
            _log_warning(f"Could not delete legacy all-sequences manifest. Error: {exc}")
        _log(f"Export finished. Wrote {len(written_sequence_paths)} sequence manifest(s), {total_shot_count} total shot row(s).")
        return sequences_root_path
    except Exception as exc:
        _log_error(str(exc))
        return ""
