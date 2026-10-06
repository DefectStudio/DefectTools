"""
Import one reviewed Shot Manager sequence manifest into Unreal.

Blueprint / Execute Python usage:
    import unreal
    import import_sequences_manifest
    import importlib

    importlib.reload(import_sequences_manifest)
    result = import_sequences_manifest.run(sequence_name)

Reads:
    [SequencesRoot]/[SEQ]/[seq]_sequence_shots_manifest_updated.json

Updates every matching BP_ShotDataAsset in that sequence:
    IsActive
    ShotOrderNumber
"""

import importlib
import json
import os

import unreal

import get_outputFolder
import get_showname


LOG_PREFIX = "[ImportSequencesManifest]"
UPDATED_SEQUENCE_MANIFEST_SUFFIX = "_sequence_shots_manifest_updated.json"
IS_ACTIVE_PROPERTY = "IsActive"
SHOT_ORDER_PROPERTY = "ShotOrderNumber"


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


def _sanitize_sequence_name(value):
    sequence_name = _sanitize_name(value, "sequence_name").upper()
    if len(sequence_name) != 3 or not sequence_name.isalnum():
        raise ValueError(
            f"Invalid sequence_name: expected exactly three letters or numbers, "
            f"got {value!r}."
        )
    return sequence_name


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "active"):
        return True
    if text in ("0", "false", "no", "n", "inactive", ""):
        return False
    return bool(value)


def _coerce_int(value, label, shot_name):
    if isinstance(value, bool):
        raise ValueError(f"Invalid {label} for shot '{shot_name}': expected int, got bool {value!r}")
    try:
        return int(str(value).strip())
    except Exception:
        raise ValueError(f"Invalid {label} for shot '{shot_name}': {value!r}")


def _read_json_file(json_path):
    with open(json_path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {json_path}")
    return data


def _reload_dependencies():
    importlib.reload(get_outputFolder)
    importlib.reload(get_showname)


def _get_default_sequences_root_path():
    sequences_root_path = _normalize_path(get_outputFolder.run())
    if not sequences_root_path:
        raise RuntimeError("Could not resolve OutputPath from QuickWidgetToolsSettings.ini.")
    return sequences_root_path


def _get_active_show_name():
    show_name = _sanitize_name(get_showname.run(), "active show_name")
    return show_name[1:] if show_name.startswith("_") else show_name


def _get_updated_sequence_manifest_path(sequences_root_path, sequence_name):
    if not os.path.isdir(sequences_root_path):
        raise RuntimeError(f"Sequences root folder does not exist: {sequences_root_path}")
    manifest_filename = f"{sequence_name.lower()}{UPDATED_SEQUENCE_MANIFEST_SUFFIX}"
    return os.path.normpath(
        os.path.join(sequences_root_path, sequence_name, manifest_filename)
    )


def _build_shot_data_asset_path(show_name, sequence_name, shot_name):
    normalized_show_name = show_name[1:] if show_name.startswith("_") else show_name
    asset_name = f"{shot_name}_Data"
    return f"/Game/_{normalized_show_name}/Sequences/{sequence_name}/{shot_name}/{asset_name}.{asset_name}"


def _find_shot_data_asset(show_name, sequence_name, shot_name):
    asset_path = _build_shot_data_asset_path(show_name, sequence_name, shot_name)
    shot_data_asset = unreal.load_asset(asset_path)
    if shot_data_asset:
        return shot_data_asset, asset_path

    normalized_show_name = show_name[1:] if show_name.startswith("_") else show_name
    shot_folder_path = f"/Game/_{normalized_show_name}/Sequences/{sequence_name}/{shot_name}"
    asset_name = f"{shot_name}_Data"
    expected_suffix = f"/{asset_name}.{asset_name}"

    try:
        candidate_paths = unreal.EditorAssetLibrary.list_assets(shot_folder_path, recursive=False, include_folder=False)
    except Exception:
        candidate_paths = []

    for candidate_path in candidate_paths:
        candidate_text = str(candidate_path)
        if not candidate_text.endswith(expected_suffix):
            continue
        shot_data_asset = unreal.load_asset(candidate_text)
        if shot_data_asset:
            return shot_data_asset, candidate_text

    return None, asset_path


def _set_asset_properties(shot_data_asset, is_active, shot_order_number):
    changed = False

    current_is_active = _coerce_bool(shot_data_asset.get_editor_property(IS_ACTIVE_PROPERTY))
    if current_is_active != is_active:
        shot_data_asset.set_editor_property(IS_ACTIVE_PROPERTY, is_active)
        changed = True

    current_shot_order_number = int(shot_data_asset.get_editor_property(SHOT_ORDER_PROPERTY))
    if current_shot_order_number != shot_order_number:
        shot_data_asset.set_editor_property(SHOT_ORDER_PROPERTY, shot_order_number)
        changed = True

    if not changed:
        return False

    save_ok = unreal.EditorAssetLibrary.save_loaded_asset(shot_data_asset)
    if not save_ok:
        raise RuntimeError(f"Failed to save asset: {shot_data_asset.get_path_name()}")

    return True


def _build_manifest_shot_rows(manifest_path, expected_show_name, expected_sequence_name):
    manifest_data = _read_json_file(manifest_path)
    manifest_type = str(manifest_data.get("manifest_type") or "").strip()
    if manifest_type and manifest_type != "sequence_shots_manifest":
        raise ValueError(f"Unsupported manifest_type in {manifest_path}: {manifest_type!r}")

    show_name = _sanitize_name(manifest_data.get("show_name"), "show_name")
    show_name = show_name[1:] if show_name.startswith("_") else show_name
    sequence_name = _sanitize_sequence_name(manifest_data.get("sequence_name"))
    if show_name.lower() != expected_show_name.lower():
        raise ValueError(
            f"Manifest show_name is {show_name!r}, but the active Unreal show is "
            f"{expected_show_name!r}."
        )
    if sequence_name != expected_sequence_name:
        raise ValueError(
            f"Manifest sequence_name is {sequence_name!r}, expected "
            f"{expected_sequence_name!r}."
        )
    shots = manifest_data.get("shots") or []
    if not isinstance(shots, list):
        raise ValueError(f"Manifest 'shots' field must be a list: {manifest_path}")

    rows = []
    seen_shot_names = set()
    for shot_data in shots:
        if not isinstance(shot_data, dict):
            raise ValueError(f"Manifest contains a non-object shot row: {manifest_path}")
        shot_name = _sanitize_name(shot_data.get("shot_name"), "shot_name")
        if shot_name in seen_shot_names:
            raise ValueError(f"Manifest contains duplicate shot_name: {shot_name}")
        seen_shot_names.add(shot_name)
        row_sequence_name = _sanitize_sequence_name(
            shot_data.get("sequence_name") or sequence_name
        )
        row_show_name = _sanitize_name(shot_data.get("show_name") or show_name, "show_name")
        row_show_name = row_show_name[1:] if row_show_name.startswith("_") else row_show_name
        if row_sequence_name != expected_sequence_name:
            raise ValueError(
                f"Shot '{shot_name}' belongs to sequence {row_sequence_name!r}, "
                f"expected {expected_sequence_name!r}."
            )
        if row_show_name.lower() != expected_show_name.lower():
            raise ValueError(
                f"Shot '{shot_name}' belongs to show {row_show_name!r}, expected "
                f"{expected_show_name!r}."
            )
        if not shot_name.upper().startswith(f"{expected_sequence_name}_"):
            raise ValueError(
                f"Shot name '{shot_name}' does not match sequence "
                f"{expected_sequence_name}."
            )
        is_active = _coerce_bool(shot_data.get("is_active", shot_data.get("is_active_value")))
        shot_order_number = _coerce_int(shot_data.get("order"), "order", shot_name)
        rows.append(
            {
                "show_name": row_show_name,
                "sequence_name": row_sequence_name,
                "shot_name": shot_name,
                "is_active": is_active,
                "shot_order_number": shot_order_number,
                "manifest_path": manifest_path,
            }
        )
    return rows


def _preflight_shot_assets(shot_rows):
    resolved_rows = []
    missing_assets = []

    for shot_row in shot_rows:
        show_name = shot_row["show_name"]
        sequence_name = shot_row["sequence_name"]
        shot_name = shot_row["shot_name"]
        shot_data_asset, asset_path = _find_shot_data_asset(
            show_name,
            sequence_name,
            shot_name,
        )
        if not shot_data_asset:
            missing_assets.append(asset_path)
            continue

        try:
            shot_data_asset.get_editor_property(IS_ACTIVE_PROPERTY)
            current_order = shot_data_asset.get_editor_property(SHOT_ORDER_PROPERTY)
            if isinstance(current_order, bool):
                raise TypeError("ShotOrderNumber is bool, expected int")
            int(current_order)
        except Exception as exc:
            raise RuntimeError(
                f"BP_ShotDataAsset for '{shot_name}' does not expose valid "
                f"{IS_ACTIVE_PROPERTY}/{SHOT_ORDER_PROPERTY} properties: {exc}"
            )

        resolved_row = dict(shot_row)
        resolved_row["shot_data_asset"] = shot_data_asset
        resolved_row["asset_path"] = asset_path
        resolved_rows.append(resolved_row)

    return resolved_rows, missing_assets


def run(sequence_name, sequences_root_path=None):
    """
    Import one sequence's *_sequence_shots_manifest_updated.json file.

    Args:
        sequence_name (str): Three-character sequence name, for example "JNG".
        sequences_root_path (str | None): Optional override for the sequences root.

    Returns:
        dict: Import summary. success is True only when every manifest shot was
        found and updated or already matched.
    """
    summary = {
        "success": False,
        "sequence_name": "",
        "manifest_path": "",
        "manifest_count": 0,
        "shot_count": 0,
        "updated_count": 0,
        "unchanged_count": 0,
        "missing_asset_count": 0,
        "failed_count": 0,
        "missing_assets": [],
        "failed_shots": [],
        "error": "",
    }

    try:
        _reload_dependencies()
        clean_sequence_name = _sanitize_sequence_name(sequence_name)
        active_show_name = _get_active_show_name()
        root_path = (
            _normalize_path(sequences_root_path)
            if sequences_root_path
            else _get_default_sequences_root_path()
        )
        manifest_path = _get_updated_sequence_manifest_path(
            root_path,
            clean_sequence_name,
        )
        summary["sequence_name"] = clean_sequence_name
        summary["manifest_path"] = manifest_path

        if not os.path.isfile(manifest_path):
            raise FileNotFoundError(
                f"Updated sequence manifest does not exist: {manifest_path}"
            )

        summary["manifest_count"] = 1
        shot_rows = _build_manifest_shot_rows(
            manifest_path,
            active_show_name,
            clean_sequence_name,
        )
        summary["shot_count"] = len(shot_rows)

        resolved_rows, missing_assets = _preflight_shot_assets(shot_rows)
        if missing_assets:
            summary["missing_asset_count"] = len(missing_assets)
            summary["missing_assets"] = missing_assets
            summary["error"] = (
                f"Preflight found {len(missing_assets)} missing BP_ShotDataAsset "
                f"file(s). No assets were changed."
            )
            for asset_path in missing_assets:
                _log_warning(f"Missing BP_ShotDataAsset: {asset_path}")
            _log_error(summary["error"])
            return summary

        _log(
            f"Importing {len(resolved_rows)} shot row(s) for sequence "
            f"'{clean_sequence_name}' from: {manifest_path}"
        )
        for shot_row in resolved_rows:
            shot_name = shot_row["shot_name"]
            shot_label = f"{clean_sequence_name}:{shot_name}"
            try:
                changed = _set_asset_properties(
                    shot_row["shot_data_asset"],
                    shot_row["is_active"],
                    shot_row["shot_order_number"],
                )
                if changed:
                    summary["updated_count"] += 1
                    _log(
                        f"Updated {shot_label}: "
                        f"IsActive={shot_row['is_active']!r}, "
                        f"ShotOrderNumber={shot_row['shot_order_number']!r}"
                    )
                else:
                    summary["unchanged_count"] += 1
            except Exception as exc:
                summary["failed_count"] += 1
                summary["failed_shots"].append(f"{shot_label}: {exc}")
                _log_error(f"Failed importing {shot_label}: {exc}")

        summary["success"] = summary["failed_count"] == 0
        if not summary["success"]:
            summary["error"] = (
                f"Failed to update {summary['failed_count']} shot asset(s)."
            )
        _log(f"Single-sequence import finished: {summary}")
        return summary
    except Exception as exc:
        summary["failed_count"] += 1
        summary["failed_shots"].append(str(exc))
        summary["error"] = str(exc)
        _log_error(str(exc))
        return summary


if __name__ == "__main__":
    _log(
        "Module loaded. Call run(sequence_name) or "
        "run(sequence_name, sequences_root_path)."
    )
