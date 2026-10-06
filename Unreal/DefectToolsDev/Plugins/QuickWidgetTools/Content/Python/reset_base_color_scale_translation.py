"""
reset_base_color_scale_translation.py

Unreal Editor Python helper for WBP_06_AssetConsolidator.

Scans materials used by loaded level/sublevel Static Mesh components, resets the
BaseColorScaleTranslation vector parameter to its default value, and turns off the
matching BaseColorScaleTranslation adjuster parameter where found.

Default mode is DRY RUN.
"""
from __future__ import annotations

import csv
import importlib
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import unreal
import analyze_duplicate_materials

importlib.reload(analyze_duplicate_materials)

LOG_PREFIX = "[AssetConsolidator MaterialFix]"

VECTOR_PARAMETER_NAME = "BaseColorScaleTranslation"
DEFAULT_VECTOR_VALUE = (1.0, 1.0, 0.0, 0.0)

# The first entry is the expected project parameter name. The additional names are
# harmless fallbacks; they are only changed if the parameter is actually found on
# the material interface.
DEFAULT_ADJUSTER_PARAMETER_NAMES = (
    "UseBaseColorScaleTranslation",
    "UseBaseColorScaleTranslationAdjuster",
    "EnableBaseColorScaleTranslation",
    "BaseColorScaleTranslationEnabled",
    "BaseColorScaleTranslationAdjuster",
)


# Shared analyzer helpers.
_asset_path = analyze_duplicate_materials._asset_path
_object_name = analyze_duplicate_materials._object_name
_class_name = analyze_duplicate_materials._class_name
_get_all_loaded_level_actors = analyze_duplicate_materials._get_all_loaded_level_actors
_get_static_mesh_components = analyze_duplicate_materials._get_static_mesh_components
_component_static_mesh = analyze_duplicate_materials._component_static_mesh
_get_static_materials = analyze_duplicate_materials._get_static_materials
_static_material_interface = analyze_duplicate_materials._static_material_interface
_component_material_count = analyze_duplicate_materials._component_material_count
_component_material = analyze_duplicate_materials._component_material
_actor_level_info = analyze_duplicate_materials._actor_level_info
_discover_open_world_levels = analyze_duplicate_materials._discover_open_world_levels
_format_level_names = analyze_duplicate_materials._format_level_names


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _linear_color_from_tuple(value: Sequence[float]) -> unreal.LinearColor:
    values = list(value) + [0.0, 0.0, 0.0, 0.0]
    return unreal.LinearColor(float(values[0]), float(values[1]), float(values[2]), float(values[3]))


def _normalize_scalar(value: Any) -> str:
    if value is None:
        return "<None>"
    try:
        return f"{round(float(value), 6):.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _normalize_vector(value: Any) -> str:
    if value is None:
        return "<None>"
    try:
        if isinstance(value, (tuple, list)):
            values = list(value)
        else:
            values = [value.r, value.g, value.b, value.a]
        return "(" + ", ".join(_normalize_scalar(item) for item in values[:4]) + ")"
    except Exception:
        return str(value)


def _get_editor_asset_library() -> Optional[Any]:
    return getattr(unreal, "EditorAssetLibrary", None)


def _is_material_instance(material: Any) -> bool:
    class_name = _class_name(material).lower()
    return "materialinstance" in class_name or "material_instance" in class_name


def _parameter_names(material: Any, function_names: Sequence[str]) -> Optional[set]:
    """Return a set of parameter names, or None if this UE build lacks the query function."""
    for function_name in function_names:
        function = getattr(unreal.MaterialEditingLibrary, function_name, None)
        if not function:
            continue
        try:
            return {str(name) for name in function(material)}
        except Exception:
            continue
    return None


def _vector_parameter_names(material: Any) -> Optional[set]:
    return _parameter_names(material, ("get_vector_parameter_names", "get_material_vector_parameter_names"))


def _scalar_parameter_names(material: Any) -> Optional[set]:
    return _parameter_names(material, ("get_scalar_parameter_names", "get_material_scalar_parameter_names"))


def _static_switch_parameter_names(material: Any) -> Optional[set]:
    return _parameter_names(material, ("get_static_switch_parameter_names", "get_material_static_switch_parameter_names"))


def _get_vector_parameter_value(material: Any, parameter_name: str) -> Any:
    try:
        return unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material, parameter_name)
    except Exception:
        return None


def _get_scalar_parameter_value(material: Any, parameter_name: str) -> Any:
    try:
        return unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(material, parameter_name)
    except Exception:
        return None


def _set_vector_parameter(material: Any, parameter_name: str, value: Sequence[float], dry_run: bool) -> Dict[str, Any]:
    vector_names = _vector_parameter_names(material)
    exists = vector_names is None or parameter_name in vector_names
    before = _get_vector_parameter_value(material, parameter_name) if exists else None

    result = {
        "parameter": parameter_name,
        "type": "VECTOR",
        "exists": exists,
        "before": _normalize_vector(before),
        "after": _normalize_vector(value),
        "status": "DRY_RUN" if dry_run and exists else "SKIPPED_NOT_FOUND",
        "error": "",
    }

    if not exists:
        return result
    if dry_run:
        return result

    try:
        material.modify()
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
            material,
            parameter_name,
            _linear_color_from_tuple(value),
        )
        result["status"] = "SUCCESS"
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)
    return result


def _set_scalar_adjuster(material: Any, parameter_name: str, off_value: float, dry_run: bool) -> Dict[str, Any]:
    scalar_names = _scalar_parameter_names(material)
    exists = scalar_names is None or parameter_name in scalar_names
    before = _get_scalar_parameter_value(material, parameter_name) if exists else None

    result = {
        "parameter": parameter_name,
        "type": "SCALAR",
        "exists": exists,
        "before": _normalize_scalar(before),
        "after": _normalize_scalar(off_value),
        "status": "DRY_RUN" if dry_run and exists else "SKIPPED_NOT_FOUND",
        "error": "",
    }

    if not exists:
        return result
    if dry_run:
        return result

    try:
        material.modify()
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(
            material,
            parameter_name,
            float(off_value),
        )
        result["status"] = "SUCCESS"
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)
    return result


def _set_static_switch_adjuster(material: Any, parameter_name: str, off_value: bool, dry_run: bool) -> Dict[str, Any]:
    switch_names = _static_switch_parameter_names(material)
    exists = switch_names is not None and parameter_name in switch_names

    result = {
        "parameter": parameter_name,
        "type": "STATIC_SWITCH",
        "exists": exists,
        "before": "<Unknown>",
        "after": str(bool(off_value)),
        "status": "DRY_RUN" if dry_run and exists else "SKIPPED_NOT_FOUND",
        "error": "",
    }

    if not exists:
        return result
    if dry_run:
        return result

    setter = getattr(unreal.MaterialEditingLibrary, "set_material_instance_static_switch_parameter_value", None)
    if not setter:
        result["status"] = "ERROR"
        result["error"] = "MaterialEditingLibrary.set_material_instance_static_switch_parameter_value is unavailable."
        return result

    try:
        material.modify()
        setter(material, parameter_name, bool(off_value))
        result["status"] = "SUCCESS"
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)
    return result


def _update_material_instance(material: Any) -> None:
    try:
        unreal.MaterialEditingLibrary.update_material_instance(material)
    except Exception:
        pass
    try:
        material.post_edit_change()
    except Exception:
        pass
    try:
        material.mark_package_dirty()
    except Exception:
        pass


def _save_material_asset(material: Any) -> bool:
    editor_asset_library = _get_editor_asset_library()
    if not editor_asset_library:
        return False
    try:
        return bool(editor_asset_library.save_loaded_asset(material, only_if_is_dirty=True))
    except Exception:
        try:
            return bool(editor_asset_library.save_asset(_asset_path(material), only_if_is_dirty=True))
        except Exception:
            return False


def _collect_open_level_materials() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]], int]:
    actors = _get_all_loaded_level_actors()
    discovered_level_infos = _discover_open_world_levels()
    material_records: Dict[str, Dict[str, Any]] = {}
    level_infos_by_package: Dict[str, Dict[str, str]] = {}
    material_slot_usage_count = 0

    def ensure_record(material: Any, actor_name: str, static_mesh_name: str, level_info: Dict[str, str]) -> Dict[str, Any]:
        material_path = _asset_path(material)
        if material_path not in material_records:
            material_records[material_path] = {
                "asset": material,
                "asset_path": material_path,
                "asset_name": _object_name(material),
                "asset_class": _class_name(material),
                "slot_usage_count": 0,
                "levels": set(),
                "level_package_paths": set(),
                "example_actors": [],
                "example_meshes": [],
            }
        record = material_records[material_path]
        record["slot_usage_count"] += 1
        record["levels"].add(level_info.get("display_name", "<UnknownLevel>"))
        record["level_package_paths"].add(level_info.get("package_path", "<UnknownLevel>"))
        if len(record["example_actors"]) < 10:
            record["example_actors"].append(actor_name)
        if static_mesh_name not in record["example_meshes"] and len(record["example_meshes"]) < 10:
            record["example_meshes"].append(static_mesh_name)
        return record

    for actor in actors:
        if not actor:
            continue
        actor_name = _object_name(actor)
        level_info = _actor_level_info(actor)
        level_package_path = level_info.get("package_path", "<UnknownLevel>")
        level_infos_by_package.setdefault(level_package_path, level_info)

        for component in _get_static_mesh_components(actor):
            static_mesh = _component_static_mesh(component)
            static_mesh_name = _object_name(static_mesh) if static_mesh else "<None>"

            # Materials actually used by component slots, including component overrides.
            for material_index in range(_component_material_count(component)):
                material_slot_usage_count += 1
                material = _component_material(component, material_index)
                if material:
                    ensure_record(material, actor_name, static_mesh_name, level_info)

            # Also include default Static Mesh asset slot materials in case some are not reached
            # by get_material() on this UE build.
            if static_mesh:
                for static_material in _get_static_materials(static_mesh):
                    material = _static_material_interface(static_material)
                    if material:
                        ensure_record(material, actor_name, static_mesh_name, level_info)

    actor_level_infos = sorted(level_infos_by_package.values(), key=lambda item: item.get("display_name", ""))
    return material_records, actor_level_infos, discovered_level_infos, material_slot_usage_count


def _serializable_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_path": record["asset_path"],
        "asset_name": record["asset_name"],
        "asset_class": record["asset_class"],
        "slot_usage_count": record["slot_usage_count"],
        "levels": sorted(record["levels"]),
        "level_package_paths": sorted(record["level_package_paths"]),
        "example_actors": record["example_actors"],
        "example_meshes": record["example_meshes"],
    }


def _write_reports(results: Dict[str, Any], operations: Sequence[Dict[str, Any]], dry_run: bool) -> Tuple[str, str]:
    project_saved_dir = unreal.Paths.project_saved_dir()
    report_dir = os.path.join(project_saved_dir, "AssetConsolidator")
    os.makedirs(report_dir, exist_ok=True)

    suffix = "dry_run" if dry_run else "executed"
    json_path = os.path.join(report_dir, f"base_color_scale_translation_reset_{suffix}.json")
    csv_path = os.path.join(report_dir, f"base_color_scale_translation_reset_{suffix}.csv")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(results, json_file, indent=2, sort_keys=True)

    fieldnames = [
        "status",
        "material_path",
        "material_name",
        "material_class",
        "slot_usage_count",
        "levels",
        "vector_parameter",
        "vector_status",
        "vector_before",
        "vector_after",
        "adjuster_results",
        "saved",
        "error",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for operation in operations:
            writer.writerow({key: operation.get(key, "") for key in fieldnames})

    return json_path, csv_path


def reset_base_color_scale_translation_on_open_level_materials(
    dry_run: bool = True,
    write_report: bool = True,
    save_dirty_assets: bool = False,
    vector_parameter_name: str = VECTOR_PARAMETER_NAME,
    vector_value: Sequence[float] = DEFAULT_VECTOR_VALUE,
    adjuster_parameter_names: Sequence[str] = DEFAULT_ADJUSTER_PARAMETER_NAMES,
    adjuster_off_value: float = 0.0,
    try_static_switch_adjusters: bool = True,
    max_log_materials: int = 25,
) -> Dict[str, Any]:
    """
    Reset BaseColorScaleTranslation on material instances used by open levels.

    dry_run=True reports what would change without modifying assets.
    save_dirty_assets=True saves modified material instance assets when dry_run=False.
    """
    _log(f"Starting BaseColorScaleTranslation reset. Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")

    material_records, actor_level_infos, discovered_level_infos, material_slot_usage_count = _collect_open_level_materials()
    _log("Scan complete.")
    _log(f"Open world levels discovered: {len(discovered_level_infos)} - {_format_level_names(discovered_level_infos)}")
    _log(f"Actor level packages scanned: {len(actor_level_infos)} - {_format_level_names(actor_level_infos)}")
    _log(f"Material slot usages scanned: {material_slot_usage_count}")
    _log(f"Unique material assets found: {len(material_records)}")
    _log(f"Vector reset: {vector_parameter_name} = {_normalize_vector(vector_value)}")
    _log(f"Adjuster off candidates: {', '.join(str(name) for name in adjuster_parameter_names)}")

    operations: List[Dict[str, Any]] = []
    processed_count = 0
    changed_or_would_change_count = 0
    vector_found_count = 0
    adjuster_found_count = 0
    error_count = 0
    skipped_non_instance_count = 0

    transaction = None
    if not dry_run:
        transaction = unreal.ScopedEditorTransaction("AssetConsolidator: Reset BaseColorScaleTranslation Parameters")
        transaction.__enter__()

    try:
        ordered_records = sorted(material_records.values(), key=lambda item: item["asset_path"])
        for record in ordered_records:
            material = record["asset"]
            operation: Dict[str, Any] = {
                "material_path": record["asset_path"],
                "material_name": record["asset_name"],
                "material_class": record["asset_class"],
                "slot_usage_count": record["slot_usage_count"],
                "levels": ", ".join(sorted(record["levels"])),
                "vector_parameter": vector_parameter_name,
                "vector_status": "",
                "vector_before": "",
                "vector_after": _normalize_vector(vector_value),
                "adjuster_results": "",
                "saved": "",
                "status": "",
                "error": "",
            }

            if not _is_material_instance(material):
                skipped_non_instance_count += 1
                operation["status"] = "SKIPPED_NON_MATERIAL_INSTANCE"
                operations.append(operation)
                continue

            processed_count += 1
            vector_result = _set_vector_parameter(material, vector_parameter_name, vector_value, dry_run)
            operation["vector_status"] = vector_result["status"]
            operation["vector_before"] = vector_result["before"]
            operation["vector_after"] = vector_result["after"]
            if vector_result["exists"]:
                vector_found_count += 1

            adjuster_results = []
            material_adjuster_found = False
            for adjuster_name in adjuster_parameter_names:
                scalar_result = _set_scalar_adjuster(material, adjuster_name, adjuster_off_value, dry_run)
                if scalar_result["exists"]:
                    material_adjuster_found = True
                    adjuster_results.append(scalar_result)
                    continue

                if try_static_switch_adjusters:
                    switch_result = _set_static_switch_adjuster(material, adjuster_name, False, dry_run)
                    if switch_result["exists"]:
                        material_adjuster_found = True
                        adjuster_results.append(switch_result)

            if material_adjuster_found:
                adjuster_found_count += 1

            operation["adjuster_results"] = json.dumps(adjuster_results, sort_keys=True)

            operation_errors = []
            if vector_result["status"] == "ERROR":
                operation_errors.append(vector_result["error"])
            for result in adjuster_results:
                if result.get("status") == "ERROR":
                    operation_errors.append(result.get("error", ""))

            if operation_errors:
                error_count += 1
                operation["status"] = "ERROR"
                operation["error"] = " | ".join(operation_errors)
            elif vector_result["exists"] or material_adjuster_found:
                changed_or_would_change_count += 1
                operation["status"] = "DRY_RUN" if dry_run else "SUCCESS"
                if not dry_run:
                    _update_material_instance(material)
                    if save_dirty_assets:
                        operation["saved"] = str(_save_material_asset(material))
            else:
                operation["status"] = "SKIPPED_NO_MATCHING_PARAMETERS"

            operations.append(operation)
    finally:
        if transaction:
            transaction.__exit__(None, None, None)

    results: Dict[str, Any] = {
        "dry_run": dry_run,
        "vector_parameter_name": vector_parameter_name,
        "vector_value": list(vector_value),
        "adjuster_parameter_names": list(adjuster_parameter_names),
        "adjuster_off_value": adjuster_off_value,
        "material_slot_usage_count": material_slot_usage_count,
        "unique_material_asset_count": len(material_records),
        "material_instance_assets_processed": processed_count,
        "skipped_non_material_instance_count": skipped_non_instance_count,
        "materials_with_vector_parameter": vector_found_count,
        "materials_with_adjuster_parameter": adjuster_found_count,
        "materials_changed_or_would_change": changed_or_would_change_count,
        "error_count": error_count,
        "actor_level_count": len(actor_level_infos),
        "actor_levels_scanned": _format_level_names(actor_level_infos),
        "actor_level_details": actor_level_infos,
        "open_world_level_count": len(discovered_level_infos),
        "open_world_levels_detected": _format_level_names(discovered_level_infos),
        "open_world_level_details": discovered_level_infos,
        "materials": [_serializable_record(record) for record in sorted(material_records.values(), key=lambda item: item["asset_path"])],
        "operations": operations,
    }

    _log(f"Material instance assets processed: {processed_count}")
    _log(f"Materials with {vector_parameter_name}: {vector_found_count}")
    _log(f"Materials with adjuster parameter found: {adjuster_found_count}")
    _log(f"Materials {'that would be changed' if dry_run else 'changed'}: {changed_or_would_change_count}")
    _log(f"Errors: {error_count}")

    for operation in operations[:max_log_materials]:
        if operation["status"] in ("DRY_RUN", "SUCCESS", "ERROR"):
            _log(
                f"{operation['status']}: {operation['material_name']} | "
                f"{vector_parameter_name} {operation['vector_before']} -> {operation['vector_after']} | "
                f"levels: {operation['levels']}"
            )
    if len(operations) > max_log_materials:
        _log(f"...and {len(operations) - max_log_materials} more material asset(s). See report files for full details.")

    if write_report:
        json_path, csv_path = _write_reports(results, operations, dry_run)
        _log(f"Wrote JSON report: {json_path}")
        _log(f"Wrote CSV report:  {csv_path}")

    if not dry_run and save_dirty_assets:
        _log("Requested save of dirty material assets.")

    _log("BaseColorScaleTranslation reset complete.")
    return results


if __name__ == "__main__":
    reset_base_color_scale_translation_on_open_level_materials(dry_run=True)
