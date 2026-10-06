from __future__ import annotations

import importlib
import json
import os
import tempfile

import unreal

import export_sequences_manifest_impl
import get_outputFolder
import get_showname


LOG_PREFIX = "[ShotOrderNumbersClean]"
SHOT_ORDER_PROPERTY = "ShotOrderNumber"
SEQUENCE_MANIFEST_SUFFIX = "_sequence_shots_manifest.json"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _normalize_disk_path(path_value):
    value = str(path_value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    value = value.replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")
    return value.rstrip("/")


def _sanitize_name(value, label):
    cleaned = "".join(
        character
        for character in str(value or "").strip()
        if character.isalnum() or character == "_"
    )
    if not cleaned:
        raise ValueError(
            f"Invalid {label}: value is empty after sanitizing. Raw value: {value!r}"
        )
    return cleaned


def _coerce_int(value, label):
    if isinstance(value, bool):
        raise ValueError(f"Invalid {label}: expected int, got bool {value!r}")
    try:
        return int(str(value).strip())
    except Exception:
        raise ValueError(f"Invalid {label}: {value!r}")


def _reload_dependencies():
    importlib.reload(export_sequences_manifest_impl)
    importlib.reload(get_outputFolder)
    importlib.reload(get_showname)


def _get_show_name():
    show_name = str(get_showname.run() or "").strip()
    if not show_name:
        raise RuntimeError("Could not resolve the active show from get_showname.run().")
    return _sanitize_name(show_name, "show_name")


def _get_sequences_root_path(sequences_root_path=None):
    raw_path = sequences_root_path if sequences_root_path else get_outputFolder.run()
    root_path = _normalize_disk_path(raw_path)
    if not root_path:
        raise RuntimeError("Could not resolve OutputPath from QuickWidgetToolsSettings.ini.")
    if not os.path.isdir(root_path):
        raise RuntimeError(f"Sequences root folder does not exist: {root_path}")
    return os.path.normpath(root_path)


def _get_show_sequences_asset_root(show_name):
    normalized_show_name = show_name[1:] if show_name.startswith("_") else show_name
    return f"/Game/_{normalized_show_name}/Sequences"


def _split_asset_path(asset_path, sequences_asset_root):
    objectless_path = str(asset_path).split(".", 1)[0]
    relative_path = objectless_path[len(sequences_asset_root):].strip("/")
    path_parts = relative_path.split("/")
    if len(path_parts) != 3:
        return None

    sequence_name, shot_name, asset_name = path_parts
    if asset_name != f"{shot_name}_Data":
        return None
    if not shot_name.upper().startswith(f"{sequence_name.upper()}_"):
        return None

    return sequence_name.upper(), shot_name


def _discover_shot_assets(show_name):
    sequences_asset_root = _get_show_sequences_asset_root(show_name)
    candidate_paths = unreal.EditorAssetLibrary.list_assets(
        sequences_asset_root,
        recursive=True,
        include_folder=False,
    )

    rows = []
    for candidate_path in sorted(candidate_paths, key=lambda value: str(value).lower()):
        parsed_path = _split_asset_path(candidate_path, sequences_asset_root)
        if parsed_path is None:
            continue

        sequence_name, shot_name = parsed_path
        shot_asset = unreal.load_asset(candidate_path)
        if not shot_asset:
            raise RuntimeError(f"Could not load expected shot data asset: {candidate_path}")

        try:
            original_order = _coerce_int(
                shot_asset.get_editor_property(SHOT_ORDER_PROPERTY),
                f"{SHOT_ORDER_PROPERTY} on {candidate_path}",
            )
        except Exception as exc:
            raise RuntimeError(
                f"Expected shot data asset does not expose a valid "
                f"{SHOT_ORDER_PROPERTY}: {candidate_path}. Error: {exc}"
            )

        rows.append(
            {
                "asset": shot_asset,
                "asset_path": str(candidate_path),
                "sequence_name": sequence_name,
                "shot_name": shot_name,
                "original_order": original_order,
                "repaired_order": original_order,
                "final_order": None,
            }
        )

    if not rows:
        raise RuntimeError(f"No shot data assets found below: {sequences_asset_root}")
    return rows


def _repair_duplicate_orders(rows):
    highest_order = max(row["original_order"] for row in rows)
    used_orders = set()
    duplicate_repairs = []

    for row in sorted(
        rows,
        key=lambda item: (item["original_order"], item["asset_path"].lower()),
    ):
        repaired_order = row["original_order"]
        if repaired_order in used_orders:
            highest_order += 1
            repaired_order = highest_order
            duplicate_repairs.append(
                {
                    "asset_path": row["asset_path"],
                    "old_order": row["original_order"],
                    "temporary_order": repaired_order,
                }
            )
        row["repaired_order"] = repaired_order
        used_orders.add(repaired_order)

    return duplicate_repairs


def _assign_preserved_orders(rows):
    sorted_rows = sorted(
        rows,
        key=lambda item: (item["repaired_order"], item["asset_path"].lower()),
    )
    for row in sorted_rows:
        row["final_order"] = row["repaired_order"]
    return sorted_rows


def _manifest_path(sequences_root_path, sequence_name):
    file_name = f"{sequence_name.lower()}{SEQUENCE_MANIFEST_SUFFIX}"
    return os.path.normpath(
        os.path.join(sequences_root_path, sequence_name, file_name)
    )


def _read_manifest(manifest_path, expected_sequence_name):
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(f"Sequence manifest does not exist: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as manifest_file:
        manifest_data = json.load(manifest_file)

    if not isinstance(manifest_data, dict):
        raise ValueError(f"JSON root must be an object: {manifest_path}")

    manifest_type = str(manifest_data.get("manifest_type") or "").strip()
    if manifest_type and manifest_type != "sequence_shots_manifest":
        raise ValueError(
            f"Unsupported manifest_type in {manifest_path}: {manifest_type!r}"
        )

    manifest_sequence = _sanitize_name(
        manifest_data.get("sequence_name"), "manifest sequence_name"
    ).upper()
    if manifest_sequence != expected_sequence_name.upper():
        raise ValueError(
            f"Manifest sequence mismatch. Expected {expected_sequence_name!r}, "
            f"found {manifest_sequence!r}: {manifest_path}"
        )

    shots = manifest_data.get("shots")
    if not isinstance(shots, list):
        raise ValueError(f"Manifest 'shots' field must be a list: {manifest_path}")

    return manifest_data


def _get_exported_shots_by_name(show_name, sequence_name):
    exported_shots = export_sequences_manifest_impl._build_sequence_shots(
        show_name,
        sequence_name,
    )
    shots_by_name = {}
    for shot_data in exported_shots:
        if not isinstance(shot_data, dict):
            raise ValueError(
                f"Exporter returned a non-object shot row for {sequence_name}: "
                f"{shot_data!r}"
            )
        shot_name = _sanitize_name(shot_data.get("shot_name"), "exported shot_name")
        if shot_name in shots_by_name:
            raise ValueError(
                f"Exporter returned duplicate shot_name {shot_name!r} for "
                f"sequence {sequence_name}."
            )
        shots_by_name[shot_name] = dict(shot_data)
    return shots_by_name


def _preflight_manifests(rows, sequences_root_path, show_name):
    rows_by_sequence = {}
    for row in rows:
        rows_by_sequence.setdefault(row["sequence_name"], []).append(row)

    manifest_records = []
    for sequence_name in sorted(rows_by_sequence):
        sequence_rows = rows_by_sequence[sequence_name]
        manifest_path = _manifest_path(sequences_root_path, sequence_name)
        manifest_data = _read_manifest(manifest_path, sequence_name)

        manifest_rows_by_name = {}
        for shot_data in manifest_data["shots"]:
            if not isinstance(shot_data, dict):
                raise ValueError(f"Manifest contains a non-object shot row: {manifest_path}")
            shot_name = _sanitize_name(shot_data.get("shot_name"), "shot_name")
            if shot_name in manifest_rows_by_name:
                raise ValueError(
                    f"Manifest contains duplicate shot_name {shot_name!r}: {manifest_path}"
                )
            manifest_rows_by_name[shot_name] = shot_data

        asset_names = {row["shot_name"] for row in sequence_rows}
        manifest_names = set(manifest_rows_by_name)
        missing_json_rows = sorted(asset_names - manifest_names)
        orphan_json_rows = sorted(manifest_names - asset_names)
        if orphan_json_rows:
            raise ValueError(
                f"Asset/manifest shot mismatch for {sequence_name}. "
                f"JSON rows without assets={orphan_json_rows}; path={manifest_path}"
            )

        added_shot_names = []
        if missing_json_rows:
            exported_shots_by_name = _get_exported_shots_by_name(
                show_name,
                sequence_name,
            )
            missing_export_rows = sorted(
                set(missing_json_rows) - set(exported_shots_by_name)
            )
            if missing_export_rows:
                raise ValueError(
                    f"Could not build complete JSON rows for Unreal shot assets "
                    f"{missing_export_rows} in sequence {sequence_name}. "
                    f"The existing exporter did not return those shots."
                )

            for shot_name in missing_json_rows:
                new_shot_data = dict(exported_shots_by_name[shot_name])
                manifest_data["shots"].append(new_shot_data)
                manifest_rows_by_name[shot_name] = new_shot_data
                added_shot_names.append(shot_name)
                _log(f"Prepared missing JSON row: {sequence_name}:{shot_name}")

        manifest_records.append(
            {
                "sequence_name": sequence_name,
                "path": manifest_path,
                "data": manifest_data,
                "shots_by_name": manifest_rows_by_name,
                "rows": sequence_rows,
                "added_shot_names": added_shot_names,
            }
        )

    return manifest_records


def _save_asset_orders(rows):
    updated_count = 0
    unchanged_count = 0

    for row in rows:
        current_order = _coerce_int(
            row["asset"].get_editor_property(SHOT_ORDER_PROPERTY),
            f"{SHOT_ORDER_PROPERTY} on {row['asset_path']}",
        )
        if current_order == row["final_order"]:
            unchanged_count += 1
            continue

        row["asset"].set_editor_property(SHOT_ORDER_PROPERTY, row["final_order"])
        if not unreal.EditorAssetLibrary.save_loaded_asset(row["asset"]):
            raise RuntimeError(f"Failed to save shot data asset: {row['asset_path']}")
        updated_count += 1
        _log(
            f"Asset {row['shot_name']}: {current_order} -> {row['final_order']}"
        )

    return updated_count, unchanged_count


def _write_json_atomically(path, data):
    folder_path = os.path.dirname(path)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=folder_path,
            prefix=f".{os.path.basename(path)}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(data, temporary_file, indent=4, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_path = temporary_file.name
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def _save_manifest_orders(manifest_records):
    updated_manifest_count = 0
    updated_json_row_count = 0
    added_json_row_count = 0

    for record in manifest_records:
        changed = bool(record["added_shot_names"])
        added_json_row_count += len(record["added_shot_names"])
        for row in record["rows"]:
            shot_data = record["shots_by_name"][row["shot_name"]]
            json_order = _coerce_int(
                shot_data.get("order"),
                f"JSON order for {row['shot_name']}",
            )
            if json_order == row["final_order"]:
                continue
            shot_data["order"] = row["final_order"]
            updated_json_row_count += 1
            changed = True
            _log(
                f"JSON {row['shot_name']}: {json_order} -> {row['final_order']}"
            )

        if changed:
            shots = record["data"]["shots"]
            active_count = sum(
                1
                for shot_data in shots
                if bool(shot_data.get("is_active", shot_data.get("is_active_value", 0)))
            )
            record["data"]["shot_count"] = len(shots)
            record["data"]["active_shot_count"] = active_count
            record["data"]["inactive_shot_count"] = len(shots) - active_count
            _write_json_atomically(record["path"], record["data"])
            updated_manifest_count += 1
            _log(f"Wrote manifest: {record['path']}")

    return updated_manifest_count, updated_json_row_count, added_json_row_count


def run(sequences_root_path=None):
    summary = {
        "success": False,
        "show_name": "",
        "sequences_root_path": "",
        "shot_count": 0,
        "duplicate_count": 0,
        "duplicate_repairs": [],
        "updated_asset_count": 0,
        "unchanged_asset_count": 0,
        "updated_manifest_count": 0,
        "updated_json_row_count": 0,
        "added_json_row_count": 0,
        "final_orders": {},
        "error": "",
    }

    try:
        _reload_dependencies()
        show_name = _get_show_name()
        root_path = _get_sequences_root_path(sequences_root_path)
        summary["show_name"] = show_name
        summary["sequences_root_path"] = root_path

        rows = _discover_shot_assets(show_name)
        summary["shot_count"] = len(rows)

        duplicate_repairs = _repair_duplicate_orders(rows)
        ordered_rows = _assign_preserved_orders(rows)

        # Validate every asset-to-JSON correspondence before changing either source.
        manifest_records = _preflight_manifests(
            ordered_rows,
            root_path,
            show_name,
        )

        updated_assets, unchanged_assets = _save_asset_orders(ordered_rows)
        (
            updated_manifests,
            updated_json_rows,
            added_json_rows,
        ) = _save_manifest_orders(manifest_records)

        summary["duplicate_count"] = len(duplicate_repairs)
        summary["duplicate_repairs"] = duplicate_repairs
        summary["updated_asset_count"] = updated_assets
        summary["unchanged_asset_count"] = unchanged_assets
        summary["updated_manifest_count"] = updated_manifests
        summary["updated_json_row_count"] = updated_json_rows
        summary["added_json_row_count"] = added_json_rows
        summary["final_orders"] = {
            row["shot_name"]: row["final_order"] for row in ordered_rows
        }
        summary["success"] = True

        _log(
            f"Finished: {len(ordered_rows)} shot(s), "
            f"{len(duplicate_repairs)} duplicate(s), "
            f"{updated_assets} asset update(s), "
            f"{updated_manifests} manifest update(s), "
            f"{updated_json_rows} JSON order update(s), "
            f"{added_json_rows} JSON row addition(s)."
        )
        return summary

    except Exception as exc:
        summary["error"] = str(exc)
        _log_error(str(exc))
        return summary


if __name__ == "__main__":
    _log("Module loaded. Call run() or run(sequences_root_path).")
