"""Read one shot's proposed frame range from its updated sequence manifest.

This is a read-only verification helper. It does not modify Unreal assets or JSON.

Blueprint / Execute Python usage:
    import get_json_new_frame_range
    import importlib

    importlib.reload(get_json_new_frame_range)
    result = get_json_new_frame_range.run(shot_name)

    new_start_frame = result["new_start_frame"]
    new_end_frame = result["new_end_frame"]

The sequence is derived from the shot name. For example, LOT_000_0125 reads:
    [SequencesRoot]/LOT/lot_sequence_shots_manifest_updated.json
"""

import importlib
import json
import os
import re

import unreal

import get_outputFolder


LOG_PREFIX = "[GetJsonNewFrameRange]"
UPDATED_SEQUENCE_MANIFEST_SUFFIX = "_sequence_shots_manifest_updated.json"
SHOT_NAME_PATTERN = re.compile(
    r"^(?P<sequence>[A-Za-z0-9]{3})_(?P<section>\d{3})_(?P<shot>\d{4,})$"
)


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _normalize_path(path_value):
    value = str(path_value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    return os.path.normpath(value)


def _parse_shot_name(shot_name):
    clean_shot_name = str(shot_name or "").strip().upper()
    match = SHOT_NAME_PATTERN.fullmatch(clean_shot_name)
    if not match:
        raise ValueError(
            "Invalid shot_name. Expected a name like LOT_000_0125, "
            f"got {shot_name!r}."
        )
    return clean_shot_name, match.group("sequence").upper()


def _get_sequences_root_path(sequences_root_path=None):
    if sequences_root_path:
        root_path = _normalize_path(sequences_root_path)
    else:
        importlib.reload(get_outputFolder)
        root_path = _normalize_path(get_outputFolder.run())
    if not root_path:
        raise RuntimeError(
            "Could not resolve OutputPath from QuickWidgetToolsSettings.ini."
        )
    if not os.path.isdir(root_path):
        raise FileNotFoundError(f"Sequences root folder does not exist: {root_path}")
    return root_path


def _get_manifest_path(sequences_root_path, sequence_name):
    manifest_filename = (
        f"{sequence_name.lower()}{UPDATED_SEQUENCE_MANIFEST_SUFFIX}"
    )
    return os.path.normpath(
        os.path.join(
            sequences_root_path,
            sequence_name,
            manifest_filename,
        )
    )


def _read_manifest(manifest_path, expected_sequence_name):
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(
            f"Updated sequence manifest does not exist: {manifest_path}"
        )
    with open(manifest_path, "r", encoding="utf-8") as json_file:
        manifest_data = json.load(json_file)
    if not isinstance(manifest_data, dict):
        raise ValueError(f"JSON root must be an object: {manifest_path}")

    manifest_sequence = str(
        manifest_data.get("sequence_name") or expected_sequence_name
    ).strip().upper()
    if manifest_sequence != expected_sequence_name:
        raise ValueError(
            f"Manifest sequence is {manifest_sequence!r}, expected "
            f"{expected_sequence_name!r}."
        )

    shots = manifest_data.get("shots")
    if not isinstance(shots, list):
        raise ValueError(f"Manifest 'shots' field must be a list: {manifest_path}")
    return shots


def _coerce_frame(value, field_name, shot_name):
    if isinstance(value, bool):
        raise ValueError(
            f"Invalid {field_name} for shot '{shot_name}': expected int, got bool."
        )
    try:
        return int(str(value).strip())
    except Exception:
        raise ValueError(
            f"Invalid {field_name} for shot '{shot_name}': {value!r}"
        )


def _find_shot_frame_range(shots, expected_shot_name):
    matching_rows = []
    for shot_data in shots:
        if not isinstance(shot_data, dict):
            continue
        row_shot_name = str(shot_data.get("shot_name") or "").strip().upper()
        if row_shot_name == expected_shot_name:
            matching_rows.append(shot_data)

    if not matching_rows:
        raise LookupError(
            f"Shot '{expected_shot_name}' was not found in the updated manifest."
        )
    if len(matching_rows) > 1:
        raise ValueError(
            f"Shot '{expected_shot_name}' appears more than once in the updated manifest."
        )

    shot_data = matching_rows[0]
    new_start_frame = _coerce_frame(
        shot_data.get("start_frame"),
        "start_frame",
        expected_shot_name,
    )
    new_end_frame = _coerce_frame(
        shot_data.get("end_frame"),
        "end_frame",
        expected_shot_name,
    )
    if new_end_frame < new_start_frame:
        raise ValueError(
            f"Shot '{expected_shot_name}' has end_frame {new_end_frame} before "
            f"start_frame {new_start_frame}."
        )
    return new_start_frame, new_end_frame


def run(shot_name, sequences_root_path=None):
    """Return one shot's frame range from its *_updated.json manifest.

    Args:
        shot_name (str): Shot name such as "LOT_000_0125".
        sequences_root_path (str | None): Optional test/manual root override.

    Returns:
        dict: On success, new_start_frame and new_end_frame are integers.
        On failure, they are -1 and error contains a readable explanation.
    """
    result = {
        "success": False,
        "shot_name": "",
        "sequence_name": "",
        "manifest_path": "",
        "new_start_frame": -1,
        "new_end_frame": -1,
        "error": "",
    }

    try:
        clean_shot_name, sequence_name = _parse_shot_name(shot_name)
        result["shot_name"] = clean_shot_name
        result["sequence_name"] = sequence_name

        root_path = _get_sequences_root_path(sequences_root_path)
        manifest_path = _get_manifest_path(root_path, sequence_name)
        result["manifest_path"] = manifest_path

        shots = _read_manifest(manifest_path, sequence_name)
        new_start_frame, new_end_frame = _find_shot_frame_range(
            shots,
            clean_shot_name,
        )
        result["new_start_frame"] = new_start_frame
        result["new_end_frame"] = new_end_frame
        result["success"] = True

        _log(
            f"Found {clean_shot_name} in {manifest_path}: "
            f"{new_start_frame}-{new_end_frame}"
        )
        return result
    except Exception as exc:
        result["error"] = str(exc)
        _log_error(str(exc))
        return result


if __name__ == "__main__":
    _log("Module loaded. Call run(shot_name).")
