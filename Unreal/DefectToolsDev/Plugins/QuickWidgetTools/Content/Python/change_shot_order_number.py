from __future__ import annotations

import importlib

import unreal

import shot_order_numbers_clean


LOG_PREFIX = "[ChangeShotOrderNumber]"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _sanitize_shot_name(value):
    if not isinstance(value, str):
        raise ValueError(
            f"Invalid shot_name: expected string, got {type(value).__name__}"
        )
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Invalid shot_name: value is empty.")
    if "/" in cleaned or "\\" in cleaned or "." in cleaned:
        raise ValueError(
            f"Invalid shot_name: contains unsupported path characters: {cleaned!r}"
        )
    return cleaned


def _coerce_new_order(value):
    if isinstance(value, bool):
        raise ValueError(
            f"Invalid new_shot_order_number: expected int, got bool {value!r}"
        )
    try:
        return int(str(value).strip())
    except Exception:
        raise ValueError(
            f"Invalid new_shot_order_number: expected an integer, got {value!r}"
        )


def _find_target_row(rows, shot_name):
    matches = [row for row in rows if row["shot_name"] == shot_name]
    if not matches:
        raise ValueError(f"No BP_ShotDataAsset found for shot: {shot_name}")
    if len(matches) > 1:
        paths = [row["asset_path"] for row in matches]
        raise ValueError(
            f"More than one BP_ShotDataAsset matched shot_name {shot_name!r}: {paths}"
        )
    return matches[0]


def _find_order_collisions(rows, target_row, new_order):
    return sorted(
        (
            row["shot_name"]
            for row in rows
            if row is not target_row and row["original_order"] == new_order
        ),
        key=str.lower,
    )


def _preflight_target_manifest(target_row, sequences_root_path, show_name):
    """Prepare a manifest update containing only the requested shot row."""
    sequence_name = target_row["sequence_name"]
    shot_name = target_row["shot_name"]
    manifest_path = shot_order_numbers_clean._manifest_path(
        sequences_root_path,
        sequence_name,
    )
    manifest_data = shot_order_numbers_clean._read_manifest(
        manifest_path,
        sequence_name,
    )

    matching_rows = [
        shot_data
        for shot_data in manifest_data["shots"]
        if isinstance(shot_data, dict)
        and str(shot_data.get("shot_name") or "").strip() == shot_name
    ]

    if len(matching_rows) > 1:
        raise ValueError(
            f"Manifest contains duplicate shot_name {shot_name!r}: {manifest_path}"
        )

    added_shot_names = []
    if matching_rows:
        manifest_shot_row = matching_rows[0]
    else:
        exported_shots_by_name = (
            shot_order_numbers_clean._get_exported_shots_by_name(
                show_name,
                sequence_name,
            )
        )
        if shot_name not in exported_shots_by_name:
            raise ValueError(
                f"Could not build a JSON row for {shot_name!r} in "
                f"sequence {sequence_name}."
            )
        manifest_shot_row = dict(exported_shots_by_name[shot_name])
        manifest_data["shots"].append(manifest_shot_row)
        added_shot_names.append(shot_name)

    return [
        {
            "sequence_name": sequence_name,
            "path": manifest_path,
            "data": manifest_data,
            "shots_by_name": {shot_name: manifest_shot_row},
            "rows": [target_row],
            "added_shot_names": added_shot_names,
        }
    ]


def run(shot_name, new_shot_order_number, sequences_root_path=None):
    summary = {
        "success": False,
        "shot_name": "",
        "requested_order": -1,
        "applied_order": -1,
        "was_clamped": False,
        "previous_order": -1,
        "final_order": -1,
        "shot_count": 0,
        "updated_asset_count": 0,
        "unchanged_asset_count": 0,
        "updated_manifest_count": 0,
        "updated_json_row_count": 0,
        "added_json_row_count": 0,
        "error": "",
    }

    try:
        clean_shot_name = _sanitize_shot_name(shot_name)
        requested_order = _coerce_new_order(new_shot_order_number)
        summary["shot_name"] = clean_shot_name
        summary["requested_order"] = requested_order

        importlib.reload(shot_order_numbers_clean)
        shot_order_numbers_clean._reload_dependencies()

        show_name = shot_order_numbers_clean._get_show_name()
        root_path = shot_order_numbers_clean._get_sequences_root_path(
            sequences_root_path
        )
        rows = shot_order_numbers_clean._discover_shot_assets(show_name)
        summary["shot_count"] = len(rows)

        if requested_order < 0:
            raise ValueError(
                f"new_shot_order_number must be 0 or greater. "
                f"Received: {requested_order}"
            )

        applied_order = requested_order
        summary["applied_order"] = applied_order

        target_row = _find_target_row(rows, clean_shot_name)
        previous_order = target_row["original_order"]
        target_row["final_order"] = applied_order
        target_rows = [target_row]

        collisions = _find_order_collisions(
            rows,
            target_row,
            applied_order,
        )
        if collisions:
            _log_warning(
                f"Order {applied_order} is also used by {collisions}. "
                "Those shots will not be changed."
            )

        summary["previous_order"] = previous_order
        summary["final_order"] = target_row["final_order"]

        # Prepare only this shot's manifest row. No neighboring shot rows are
        # included in either save operation.
        manifest_records = _preflight_target_manifest(
            target_row,
            root_path,
            show_name,
        )

        updated_assets, unchanged_assets = (
            shot_order_numbers_clean._save_asset_orders(target_rows)
        )
        (
            updated_manifests,
            updated_json_rows,
            added_json_rows,
        ) = shot_order_numbers_clean._save_manifest_orders(manifest_records)

        summary["updated_asset_count"] = updated_assets
        summary["unchanged_asset_count"] = unchanged_assets
        summary["updated_manifest_count"] = updated_manifests
        summary["updated_json_row_count"] = updated_json_rows
        summary["added_json_row_count"] = added_json_rows
        summary["success"] = True

        _log(
            f"Changed only {clean_shot_name} from order {previous_order} to "
            f"{target_row['final_order']}. Updated {updated_assets} target "
            f"asset(s), {updated_manifests} target manifest(s), and "
            f"{updated_json_rows} target JSON order value(s); added "
            f"{added_json_rows} missing target JSON row(s)."
        )
        return summary

    except Exception as exc:
        summary["error"] = str(exc)
        _log_error(str(exc))
        return summary


if __name__ == "__main__":
    _log(
        "Module loaded. Call run(shot_name, new_shot_order_number) or "
        "run(shot_name, new_shot_order_number, sequences_root_path)."
    )
