"""
consolidate_duplicate_static_meshes.py

Unreal Editor Python helper for WBP_06_AssetConsolidator.

Scans all currently loaded actors in the open level and loaded/open sublevels,
finds duplicate-candidate Static Mesh assets using the same signature logic as
analyze_duplicate_static_meshes.py, chooses the first mesh asset found in each
duplicate group as the keeper, and replaces level component StaticMesh references
that point at duplicate assets with the keeper.

Default mode is DRY RUN. In dry run mode this only writes a report and prints what
would be changed. It does not modify actors, components, assets, levels, or save
anything.
"""

from __future__ import annotations

import csv
import importlib
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import unreal

import analyze_duplicate_static_meshes

# Keep this hot-reload friendly when called from an Editor Utility Widget.
importlib.reload(analyze_duplicate_static_meshes)


LOG_PREFIX = "[AssetConsolidator MeshConsolidate]"


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _error(message: str) -> None:
    unreal.log_error(f"{LOG_PREFIX} {message}")


# ---------------------------------------------------------------------------
# Thin wrappers around the analyzer helpers.
# This keeps the consolidation signature locked to the Analyze button.
# ---------------------------------------------------------------------------


def _asset_path(asset: Any) -> str:
    return analyze_duplicate_static_meshes._asset_path(asset)


def _object_name(obj: Any) -> str:
    return analyze_duplicate_static_meshes._object_name(obj)


def _get_all_loaded_level_actors() -> List[Any]:
    return analyze_duplicate_static_meshes._get_all_loaded_level_actors()


def _get_static_mesh_components(actor: Any) -> List[Any]:
    return analyze_duplicate_static_meshes._get_static_mesh_components(actor)


def _component_static_mesh(component: Any) -> Optional[Any]:
    return analyze_duplicate_static_meshes._component_static_mesh(component)


def _actor_level_info(actor: Any) -> Dict[str, str]:
    return analyze_duplicate_static_meshes._actor_level_info(actor)


def _discover_open_world_levels() -> List[Dict[str, str]]:
    return analyze_duplicate_static_meshes._discover_open_world_levels()


def _format_level_names(level_infos: Sequence[Dict[str, str]]) -> str:
    return analyze_duplicate_static_meshes._format_level_names(level_infos)


def _mesh_signature(static_mesh: Any) -> Tuple[Any, ...]:
    return analyze_duplicate_static_meshes._mesh_signature(static_mesh)


def _signature_to_dict(signature: Tuple[Any, ...]) -> Dict[str, Any]:
    return analyze_duplicate_static_meshes._signature_to_dict(signature)


# ---------------------------------------------------------------------------
# Collection / grouping
# ---------------------------------------------------------------------------


def _collect_static_mesh_component_usage() -> Tuple[
    Dict[str, Dict[str, Any]],
    List[Dict[str, str]],
    List[Dict[str, str]],
    int,
]:
    """Collect every loaded level component that references a Static Mesh asset."""
    actors = _get_all_loaded_level_actors()
    discovered_level_infos = _discover_open_world_levels()

    mesh_records: Dict[str, Dict[str, Any]] = {}
    actor_level_infos_by_package: Dict[str, Dict[str, str]] = {}
    component_count = 0
    first_seen_index = 0

    for actor in actors:
        if not actor:
            continue

        actor_name = _object_name(actor)
        actor_path = _asset_path(actor)
        level_info = _actor_level_info(actor)
        level_name = level_info.get("display_name", "<UnknownLevel>")
        level_key = level_info.get("package_path") or level_name
        actor_level_infos_by_package.setdefault(level_key, level_info)

        for component in _get_static_mesh_components(actor):
            static_mesh = _component_static_mesh(component)
            if not static_mesh:
                continue

            component_count += 1
            mesh_path = _asset_path(static_mesh)
            component_path = _asset_path(component)

            if mesh_path not in mesh_records:
                mesh_records[mesh_path] = {
                    "asset": static_mesh,
                    "asset_path": mesh_path,
                    "asset_name": _object_name(static_mesh),
                    "signature": _mesh_signature(static_mesh),
                    "first_seen_index": first_seen_index,
                    "component_count": 0,
                    "levels": set(),
                    "level_package_paths": set(),
                    "example_actors": [],
                    "example_components": [],
                    "component_records": [],
                }
                first_seen_index += 1

            record = mesh_records[mesh_path]
            record["component_count"] += 1
            record["levels"].add(level_name)
            record["level_package_paths"].add(level_info.get("package_path", "<UnknownLevel>"))

            component_record = {
                "actor": actor,
                "component": component,
                "static_mesh": static_mesh,
                "static_mesh_path": mesh_path,
                "actor_name": actor_name,
                "actor_path": actor_path,
                "component_name": _object_name(component),
                "component_path": component_path,
                "level_name": level_name,
                "level_package_path": level_info.get("package_path", "<UnknownLevel>"),
            }

            record["component_records"].append(component_record)

            if len(record["example_actors"]) < 10:
                record["example_actors"].append(actor_name)

            if len(record["example_components"]) < 10:
                record["example_components"].append(component_path)

    actor_level_infos = sorted(
        actor_level_infos_by_package.values(),
        key=lambda item: item.get("display_name", ""),
    )

    return mesh_records, actor_level_infos, discovered_level_infos, component_count


def _build_consolidation_groups(mesh_records: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group mesh assets by duplicate signature.

    The keeper is the first mesh asset encountered while scanning level actors and
    components. The report groups are sorted for readability, but the keeper does
    not change after being assigned.
    """
    signature_groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)

    # Dict insertion order is first-seen order in current Python versions.
    for record in mesh_records.values():
        signature_groups[record["signature"]].append(record)

    groups: List[Dict[str, Any]] = []

    for signature, records in signature_groups.items():
        if len(records) < 2:
            continue

        records_in_first_seen_order = sorted(records, key=lambda item: int(item["first_seen_index"]))
        keeper_record = records_in_first_seen_order[0]
        duplicate_records = records_in_first_seen_order[1:]
        replaceable_component_count = sum(int(record["component_count"]) for record in duplicate_records)
        total_component_count = sum(int(record["component_count"]) for record in records_in_first_seen_order)

        groups.append(
            {
                "signature": signature,
                "signature_info": _signature_to_dict(signature),
                "keeper": keeper_record,
                "duplicates": duplicate_records,
                "assets": records_in_first_seen_order,
                "asset_count": len(records_in_first_seen_order),
                "duplicate_asset_count": len(duplicate_records),
                "replaceable_component_count": replaceable_component_count,
                "total_component_count": total_component_count,
            }
        )

    groups.sort(
        key=lambda group: (
            -int(group["replaceable_component_count"]),
            -int(group["asset_count"]),
            str(group["signature_info"].get("clean_base_name", "")),
        )
    )

    return groups


# ---------------------------------------------------------------------------
# Replacement helpers
# ---------------------------------------------------------------------------


def _replace_component_static_mesh(component: Any, keeper_mesh: Any) -> None:
    """Set a component's Static Mesh reference in a way that updates editor state."""
    component.modify()

    set_static_mesh = getattr(component, "set_static_mesh", None)
    if set_static_mesh:
        try:
            set_static_mesh(keeper_mesh)
            return
        except Exception:
            # Fall back to set_editor_property below.
            pass

    component.set_editor_property("static_mesh", keeper_mesh)


def _post_edit_changed(obj: Any) -> None:
    for method_name in ("post_edit_change", "post_edit_change_property"):
        try:
            method = getattr(obj, method_name, None)
            if method:
                method()
                return
        except Exception:
            pass


def _make_operation_record(
    group_index: int,
    keeper_record: Dict[str, Any],
    duplicate_record: Dict[str, Any],
    component_record: Dict[str, Any],
    action: str,
    status: str,
    error_message: str = "",
) -> Dict[str, Any]:
    return {
        "group_index": group_index,
        "action": action,
        "status": status,
        "error": error_message,
        "keeper_asset_path": keeper_record["asset_path"],
        "keeper_asset_name": keeper_record["asset_name"],
        "old_asset_path": duplicate_record["asset_path"],
        "old_asset_name": duplicate_record["asset_name"],
        "actor_name": component_record["actor_name"],
        "actor_path": component_record["actor_path"],
        "component_name": component_record["component_name"],
        "component_path": component_record["component_path"],
        "level_name": component_record["level_name"],
        "level_package_path": component_record["level_package_path"],
    }


def _run_consolidation(
    groups: Sequence[Dict[str, Any]],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    operation_records: List[Dict[str, Any]] = []

    transaction_context = None
    if not dry_run:
        transaction_context = unreal.ScopedEditorTransaction("AssetConsolidator: Consolidate Duplicate Static Mesh References")
        transaction_context.__enter__()

    try:
        for group_index, group in enumerate(groups, start=1):
            keeper_record = group["keeper"]
            keeper_mesh = keeper_record["asset"]

            for duplicate_record in group["duplicates"]:
                for component_record in duplicate_record["component_records"]:
                    component = component_record["component"]
                    actor = component_record["actor"]

                    if dry_run:
                        operation_records.append(
                            _make_operation_record(
                                group_index=group_index,
                                keeper_record=keeper_record,
                                duplicate_record=duplicate_record,
                                component_record=component_record,
                                action="WOULD_REPLACE_COMPONENT_STATIC_MESH",
                                status="DRY_RUN",
                            )
                        )
                        continue

                    try:
                        if actor:
                            actor.modify()

                        _replace_component_static_mesh(component, keeper_mesh)
                        _post_edit_changed(component)

                        if actor:
                            _post_edit_changed(actor)

                        operation_records.append(
                            _make_operation_record(
                                group_index=group_index,
                                keeper_record=keeper_record,
                                duplicate_record=duplicate_record,
                                component_record=component_record,
                                action="REPLACED_COMPONENT_STATIC_MESH",
                                status="SUCCESS",
                            )
                        )
                    except Exception as exc:
                        operation_records.append(
                            _make_operation_record(
                                group_index=group_index,
                                keeper_record=keeper_record,
                                duplicate_record=duplicate_record,
                                component_record=component_record,
                                action="REPLACE_COMPONENT_STATIC_MESH_FAILED",
                                status="ERROR",
                                error_message=str(exc),
                            )
                        )
    finally:
        if transaction_context:
            transaction_context.__exit__(None, None, None)

    if not dry_run:
        try:
            unreal.EditorLevelLibrary.redraw_all_viewports()
        except Exception:
            pass

    return operation_records


# ---------------------------------------------------------------------------
# Reports / logging
# ---------------------------------------------------------------------------


def _json_safe_asset_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_path": record["asset_path"],
        "asset_name": record["asset_name"],
        "first_seen_index": record["first_seen_index"],
        "component_count": record["component_count"],
        "levels": sorted(record["levels"]),
        "level_package_paths": sorted(record["level_package_paths"]),
        "example_actors": list(record["example_actors"]),
        "example_components": list(record["example_components"]),
    }


def _json_safe_group(group: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "signature_info": group["signature_info"],
        "asset_count": group["asset_count"],
        "duplicate_asset_count": group["duplicate_asset_count"],
        "total_component_count": group["total_component_count"],
        "replaceable_component_count": group["replaceable_component_count"],
        "keeper": _json_safe_asset_record(group["keeper"]),
        "duplicates": [_json_safe_asset_record(record) for record in group["duplicates"]],
        "assets": [_json_safe_asset_record(record) for record in group["assets"]],
    }


def _write_reports(report: Dict[str, Any], dry_run: bool) -> Tuple[str, str]:
    output_dir = os.path.join(unreal.Paths.project_saved_dir(), "AssetConsolidator")
    os.makedirs(output_dir, exist_ok=True)

    suffix = "dry_run" if dry_run else "executed"
    json_path = os.path.join(output_dir, f"duplicate_static_mesh_consolidation_{suffix}.json")
    csv_path = os.path.join(output_dir, f"duplicate_static_mesh_consolidation_{suffix}.csv")

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)

    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "group_index",
                "action",
                "status",
                "error",
                "level_name",
                "actor_name",
                "component_name",
                "old_asset_path",
                "keeper_asset_path",
                "component_path",
                "actor_path",
                "level_package_path",
            ]
        )

        for operation in report["operations"]:
            writer.writerow(
                [
                    operation["group_index"],
                    operation["action"],
                    operation["status"],
                    operation["error"],
                    operation["level_name"],
                    operation["actor_name"],
                    operation["component_name"],
                    operation["old_asset_path"],
                    operation["keeper_asset_path"],
                    operation["component_path"],
                    operation["actor_path"],
                    operation["level_package_path"],
                ]
            )

    return json_path, csv_path


def _log_group_summary(
    groups: Sequence[Dict[str, Any]],
    max_log_groups: int,
    max_assets_per_group_log: int,
) -> None:
    if not groups:
        _log("No duplicate static mesh candidates found. Nothing to consolidate.")
        return

    _log(f"Duplicate static mesh consolidation groups: {len(groups)}")

    for group_index, group in enumerate(groups[:max_log_groups], start=1):
        signature = group["signature_info"]
        keeper = group["keeper"]

        _log(
            f"Group {group_index}: keeper={keeper['asset_name']} | "
            f"{group['duplicate_asset_count']} duplicate mesh asset(s), "
            f"{group['replaceable_component_count']} component reference(s) to replace"
        )
        _log(
            "  Signature: "
            f"BaseName={signature['clean_base_name']} | "
            f"{signature['geometry_count_type']}={signature['geometry_count_value']} | "
            f"MaterialSlots={signature['material_slot_count']} | "
            f"Materials={signature['material_names']}"
        )
        _log(f"  Keeper: {keeper['asset_path']} (first seen; levels: {', '.join(sorted(keeper['levels']))})")

        for duplicate_record in group["duplicates"][:max_assets_per_group_log]:
            _log(
                f"    Duplicate: {duplicate_record['asset_path']} "
                f"({duplicate_record['component_count']} component(s); "
                f"levels: {', '.join(sorted(duplicate_record['levels']))})"
            )

        remaining = len(group["duplicates"]) - max_assets_per_group_log
        if remaining > 0:
            _log(f"    ...and {remaining} more duplicate asset(s) in this group.")

    remaining_groups = len(groups) - max_log_groups
    if remaining_groups > 0:
        _log(f"...and {remaining_groups} more group(s). See report files for full details.")


def _save_dirty_level_packages_if_requested(save_dirty_levels: bool, dry_run: bool) -> None:
    if dry_run or not save_dirty_levels:
        return

    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
            save_map_packages=True,
            save_content_packages=False,
        )
        _log("Requested save of dirty map packages.")
    except TypeError:
        try:
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, False)
            _log("Requested save of dirty map packages.")
        except Exception as exc:
            _warn(f"Could not save dirty map packages automatically: {exc}")
    except Exception as exc:
        _warn(f"Could not save dirty map packages automatically: {exc}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def consolidate_duplicate_static_meshes(
    dry_run: bool = True,
    write_report: bool = True,
    save_dirty_levels: bool = False,
    max_log_groups: int = 25,
    max_assets_per_group_log: int = 10,
) -> Dict[str, Any]:
    """
    Consolidate duplicate Static Mesh references in the currently loaded levels.

    Args:
        dry_run: If True, only reports planned changes. If False, modifies level
            component StaticMesh references.
        write_report: If True, writes JSON and CSV reports to Saved/AssetConsolidator.
        save_dirty_levels: If True and dry_run is False, asks Unreal to save dirty
            map packages after replacement. Default False for safety.
        max_log_groups: Maximum duplicate groups to print to the Output Log.
        max_assets_per_group_log: Maximum duplicate assets per group to log.

    Returns:
        Dictionary report containing summary, consolidation_groups, and operations.
    """
    mode_label = "DRY RUN" if dry_run else "EXECUTE"
    _log(f"Starting duplicate static mesh consolidation. Mode: {mode_label}")

    mesh_records, actor_level_infos, discovered_level_infos, component_count = _collect_static_mesh_component_usage()
    groups = _build_consolidation_groups(mesh_records)

    _log("Scan complete.")
    _log(
        "Open world levels discovered: "
        f"{len(discovered_level_infos)} - {_format_level_names(discovered_level_infos)}"
    )
    _log(
        "Actor level packages scanned: "
        f"{len(actor_level_infos)} - {_format_level_names(actor_level_infos)}"
    )
    _log(f"Static mesh components scanned: {component_count}")
    _log(f"Unique static mesh assets found: {len(mesh_records)}")
    _log(f"Duplicate candidate groups: {len(groups)}")
    _log(f"Duplicate candidate mesh assets: {sum(group['asset_count'] for group in groups)}")
    _log(f"Duplicate mesh assets that would be replaced: {sum(group['duplicate_asset_count'] for group in groups)}")
    _log(f"Component references that would be changed: {sum(group['replaceable_component_count'] for group in groups)}")

    _log_group_summary(groups, max_log_groups, max_assets_per_group_log)

    operation_records = _run_consolidation(groups, dry_run=dry_run)
    error_count = sum(1 for operation in operation_records if operation["status"] == "ERROR")
    success_count = sum(1 for operation in operation_records if operation["status"] == "SUCCESS")
    dry_run_count = sum(1 for operation in operation_records if operation["status"] == "DRY_RUN")

    _save_dirty_level_packages_if_requested(save_dirty_levels=save_dirty_levels, dry_run=dry_run)

    report = {
        "summary": {
            "mode": mode_label,
            "dry_run": dry_run,
            "actor_level_count": len(actor_level_infos),
            "actor_levels_scanned": [info["display_name"] for info in actor_level_infos],
            "actor_level_details": actor_level_infos,
            "open_world_level_count": len(discovered_level_infos),
            "open_world_levels_detected": [info["display_name"] for info in discovered_level_infos],
            "open_world_level_details": discovered_level_infos,
            "static_mesh_component_count": component_count,
            "unique_static_mesh_asset_count": len(mesh_records),
            "duplicate_group_count": len(groups),
            "duplicate_candidate_asset_count": sum(group["asset_count"] for group in groups),
            "duplicate_asset_replacement_count": sum(group["duplicate_asset_count"] for group in groups),
            "component_reference_replacement_count": sum(group["replaceable_component_count"] for group in groups),
            "operation_count": len(operation_records),
            "dry_run_operation_count": dry_run_count,
            "successful_operation_count": success_count,
            "error_count": error_count,
            "save_dirty_levels_requested": bool(save_dirty_levels),
        },
        "consolidation_groups": [_json_safe_group(group) for group in groups],
        "operations": operation_records,
    }

    if write_report:
        json_path, csv_path = _write_reports(report, dry_run=dry_run)
        _log(f"Wrote JSON report: {json_path}")
        _log(f"Wrote CSV report:  {csv_path}")

    if dry_run:
        _log(f"Dry run complete. {dry_run_count} component reference(s) would be replaced.")
    else:
        if error_count:
            _warn(f"Consolidation complete with {error_count} error(s). Successful replacements: {success_count}")
        else:
            _log(f"Consolidation complete. Successful replacements: {success_count}")

    return report


if __name__ == "__main__":
    consolidate_duplicate_static_meshes(dry_run=True)
