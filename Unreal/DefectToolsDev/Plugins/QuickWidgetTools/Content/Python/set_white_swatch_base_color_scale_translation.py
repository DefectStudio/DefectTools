"""
set_white_swatch_base_color_scale_translation.py

Unreal Editor Python helper for WBP_06_AssetConsolidator.

Scans Static Mesh components in the currently open level and loaded sublevels,
finds material instances whose BaseColorTexture resolves to the target white
swatch texture, and sets BaseColorScaleTranslation to 0.5, 0.5, 0.5, 0.5.

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

LOG_PREFIX = "[AssetConsolidator WhiteSwatchFix]"

TARGET_TEXTURE_NAME = "T_common_color_swatch_preview_preview_white_noedit"
TEXTURE_PARAMETER_NAME = "BaseColorTexture"
VECTOR_PARAMETER_NAME = "BaseColorScaleTranslation"
VECTOR_VALUE = (0.5, 0.5, 0.5, 0.5)


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
        values = values + [0.0, 0.0, 0.0, 0.0]
        return "(" + ", ".join(_normalize_scalar(item) for item in values[:4]) + ")"
    except Exception:
        return str(value)


def _linear_color_from_tuple(value: Sequence[float]) -> unreal.LinearColor:
    values = list(value) + [0.0, 0.0, 0.0, 0.0]
    return unreal.LinearColor(float(values[0]), float(values[1]), float(values[2]), float(values[3]))


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


def _texture_parameter_names(material: Any) -> Optional[set]:
    return _parameter_names(material, ("get_texture_parameter_names", "get_material_texture_parameter_names"))


def _get_texture_parameter_value(material: Any, parameter_name: str) -> Optional[Any]:
    try:
        return unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, parameter_name)
    except Exception:
        pass

    # Fallback: direct override values only. The MaterialEditingLibrary call above is
    # preferred because it resolves inherited/default material instance values.
    try:
        values = material.get_editor_property("texture_parameter_values")
        for value in values:
            try:
                parameter_info = value.get_editor_property("parameter_info")
                name = str(parameter_info.get_editor_property("name"))
                if name != parameter_name:
                    continue
                return value.get_editor_property("parameter_value")
            except Exception:
                continue
    except Exception:
        pass

    return None


def _get_vector_parameter_value(material: Any, parameter_name: str) -> Any:
    try:
        return unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material, parameter_name)
    except Exception:
        return None


def _texture_matches(texture: Any, target_texture_name: str) -> bool:
    if not texture:
        return False

    target = str(target_texture_name).lower()
    texture_name = _object_name(texture).lower()
    texture_path = _asset_path(texture).lower()

    return texture_name == target or texture_path.endswith("/" + target + "." + target)


def _set_vector_parameter(material: Any, parameter_name: str, value: Sequence[float], dry_run: bool) -> Dict[str, Any]:
    vector_names = _vector_parameter_names(material)
    exists = vector_names is None or parameter_name in vector_names
    before = _get_vector_parameter_value(material, parameter_name) if exists else None

    result = {
        "parameter": parameter_name,
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
    editor_asset_library = getattr(unreal, "EditorAssetLibrary", None)
    if not editor_asset_library:
        return False

    try:
        return bool(editor_asset_library.save_loaded_asset(material, only_if_is_dirty=True))
    except Exception:
        pass

    try:
        return bool(editor_asset_library.save_asset(_asset_path(material), only_if_is_dirty=True))
    except Exception:
        return False


def _ensure_material_record(
    material_records: Dict[str, Dict[str, Any]],
    material: Any,
    actor_name: str,
    static_mesh_name: str,
    level_info: Dict[str, str],
    source: str,
) -> Dict[str, Any]:
    material_path = _asset_path(material)
    if material_path not in material_records:
        material_records[material_path] = {
            "asset": material,
            "asset_path": material_path,
            "asset_name": _object_name(material),
            "asset_class": _class_name(material),
            "slot_usage_count": 0,
            "component_slot_usage_count": 0,
            "static_mesh_default_slot_usage_count": 0,
            "levels": set(),
            "level_package_paths": set(),
            "example_actors": [],
            "example_meshes": [],
        }

    record = material_records[material_path]
    record["slot_usage_count"] += 1
    if source == "COMPONENT_SLOT":
        record["component_slot_usage_count"] += 1
    elif source == "STATIC_MESH_DEFAULT_SLOT":
        record["static_mesh_default_slot_usage_count"] += 1

    record["levels"].add(level_info.get("display_name", "<UnknownLevel>"))
    record["level_package_paths"].add(level_info.get("package_path", "<UnknownLevel>"))
    if actor_name not in record["example_actors"] and len(record["example_actors"]) < 10:
        record["example_actors"].append(actor_name)
    if static_mesh_name not in record["example_meshes"] and len(record["example_meshes"]) < 10:
        record["example_meshes"].append(static_mesh_name)

    return record


def _collect_open_level_materials(
    include_static_mesh_default_slot_materials: bool = False,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]], int, int]:
    actors = _get_all_loaded_level_actors()
    discovered_level_infos = _discover_open_world_levels()
    material_records: Dict[str, Dict[str, Any]] = {}
    level_infos_by_package: Dict[str, Dict[str, str]] = {}
    material_slot_usage_count = 0
    static_mesh_component_count = 0

    for actor in actors:
        if not actor:
            continue

        actor_name = _object_name(actor)
        level_info = _actor_level_info(actor)
        level_package_path = level_info.get("package_path", "<UnknownLevel>")
        level_infos_by_package.setdefault(level_package_path, level_info)

        for component in _get_static_mesh_components(actor):
            static_mesh_component_count += 1
            static_mesh = _component_static_mesh(component)
            static_mesh_name = _object_name(static_mesh) if static_mesh else "<None>"

            # Active component slot materials. This includes component overrides and is
            # the important path for USD Import Into Level scenes.
            for material_index in range(_component_material_count(component)):
                material_slot_usage_count += 1
                material = _component_material(component, material_index)
                if material:
                    _ensure_material_record(
                        material_records,
                        material,
                        actor_name,
                        static_mesh_name,
                        level_info,
                        "COMPONENT_SLOT",
                    )

            if include_static_mesh_default_slot_materials and static_mesh:
                for static_material in _get_static_materials(static_mesh):
                    material_slot_usage_count += 1
                    material = _static_material_interface(static_material)
                    if material:
                        _ensure_material_record(
                            material_records,
                            material,
                            actor_name,
                            static_mesh_name,
                            level_info,
                            "STATIC_MESH_DEFAULT_SLOT",
                        )

    actor_level_infos = sorted(level_infos_by_package.values(), key=lambda item: item.get("display_name", ""))
    return material_records, actor_level_infos, discovered_level_infos, material_slot_usage_count, static_mesh_component_count


def _serializable_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_path": record["asset_path"],
        "asset_name": record["asset_name"],
        "asset_class": record["asset_class"],
        "slot_usage_count": record["slot_usage_count"],
        "component_slot_usage_count": record["component_slot_usage_count"],
        "static_mesh_default_slot_usage_count": record["static_mesh_default_slot_usage_count"],
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
    json_path = os.path.join(report_dir, f"white_swatch_base_color_scale_translation_{suffix}.json")
    csv_path = os.path.join(report_dir, f"white_swatch_base_color_scale_translation_{suffix}.csv")

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(results, json_file, indent=2, sort_keys=True)

    fieldnames = [
        "status",
        "material_path",
        "material_name",
        "material_class",
        "slot_usage_count",
        "component_slot_usage_count",
        "static_mesh_default_slot_usage_count",
        "levels",
        "texture_parameter",
        "texture_name",
        "texture_path",
        "vector_parameter",
        "vector_before",
        "vector_after",
        "saved",
        "error",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for operation in operations:
            writer.writerow({key: operation.get(key, "") for key in fieldnames})

    return json_path, csv_path


def set_white_swatch_base_color_scale_translation_on_open_level_materials(
    dry_run: bool = True,
    write_report: bool = True,
    save_dirty_assets: bool = False,
    target_texture_name: str = TARGET_TEXTURE_NAME,
    texture_parameter_name: str = TEXTURE_PARAMETER_NAME,
    vector_parameter_name: str = VECTOR_PARAMETER_NAME,
    vector_value: Sequence[float] = VECTOR_VALUE,
    include_static_mesh_default_slot_materials: bool = False,
    max_log_materials: int = 50,
) -> Dict[str, Any]:
    """
    Set BaseColorScaleTranslation on material instances used by loaded levels when
    BaseColorTexture matches the target texture.

    dry_run=True reports what would change without modifying assets.
    save_dirty_assets=True saves modified material instance assets when dry_run=False.
    include_static_mesh_default_slot_materials=False keeps the scan focused on the
    actual active component materials in the open levels/sublevels.
    """
    _log(f"Starting white swatch BaseColorScaleTranslation fix. Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")

    (
        material_records,
        actor_level_infos,
        discovered_level_infos,
        material_slot_usage_count,
        static_mesh_component_count,
    ) = _collect_open_level_materials(include_static_mesh_default_slot_materials=include_static_mesh_default_slot_materials)

    _log("Scan complete.")
    _log(f"Open world levels discovered: {len(discovered_level_infos)} - {_format_level_names(discovered_level_infos)}")
    _log(f"Actor level packages scanned: {len(actor_level_infos)} - {_format_level_names(actor_level_infos)}")
    _log(f"Static mesh components scanned: {static_mesh_component_count}")
    _log(f"Material slot usages scanned: {material_slot_usage_count}")
    _log(f"Unique material assets found: {len(material_records)}")
    _log(f"Texture match: {texture_parameter_name} = {target_texture_name}")
    _log(f"Vector set: {vector_parameter_name} = {_normalize_vector(vector_value)}")
    _log(f"include_static_mesh_default_slot_materials: {include_static_mesh_default_slot_materials}")

    operations: List[Dict[str, Any]] = []
    processed_instance_count = 0
    matched_material_count = 0
    changed_or_would_change_count = 0
    skipped_non_instance_count = 0
    skipped_texture_mismatch_count = 0
    skipped_missing_texture_parameter_count = 0
    skipped_missing_vector_parameter_count = 0
    error_count = 0

    transaction = None
    if not dry_run:
        transaction = unreal.ScopedEditorTransaction("AssetConsolidator: Set White Swatch BaseColorScaleTranslation")
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
                "component_slot_usage_count": record["component_slot_usage_count"],
                "static_mesh_default_slot_usage_count": record["static_mesh_default_slot_usage_count"],
                "levels": ", ".join(sorted(record["levels"])),
                "texture_parameter": texture_parameter_name,
                "texture_name": "",
                "texture_path": "",
                "vector_parameter": vector_parameter_name,
                "vector_before": "",
                "vector_after": _normalize_vector(vector_value),
                "saved": "",
                "status": "",
                "error": "",
            }

            if not _is_material_instance(material):
                skipped_non_instance_count += 1
                operation["status"] = "SKIPPED_NON_MATERIAL_INSTANCE"
                operations.append(operation)
                continue

            processed_instance_count += 1

            texture_names = _texture_parameter_names(material)
            texture_parameter_exists = texture_names is None or texture_parameter_name in texture_names
            if not texture_parameter_exists:
                skipped_missing_texture_parameter_count += 1
                operation["status"] = "SKIPPED_MISSING_TEXTURE_PARAMETER"
                operations.append(operation)
                continue

            texture = _get_texture_parameter_value(material, texture_parameter_name)
            if texture:
                operation["texture_name"] = _object_name(texture)
                operation["texture_path"] = _asset_path(texture)

            if not _texture_matches(texture, target_texture_name):
                skipped_texture_mismatch_count += 1
                operation["status"] = "SKIPPED_TEXTURE_MISMATCH"
                operations.append(operation)
                continue

            matched_material_count += 1

            vector_result = _set_vector_parameter(material, vector_parameter_name, vector_value, dry_run)
            operation["vector_before"] = vector_result["before"]
            operation["vector_after"] = vector_result["after"]

            if not vector_result["exists"]:
                skipped_missing_vector_parameter_count += 1
                operation["status"] = "SKIPPED_MISSING_VECTOR_PARAMETER"
                operations.append(operation)
                continue

            if vector_result["status"] == "ERROR":
                error_count += 1
                operation["status"] = "ERROR"
                operation["error"] = vector_result["error"]
                operations.append(operation)
                continue

            changed_or_would_change_count += 1
            operation["status"] = "DRY_RUN" if dry_run else "SUCCESS"

            if not dry_run:
                _update_material_instance(material)
                if save_dirty_assets:
                    operation["saved"] = str(_save_material_asset(material))

            operations.append(operation)
    finally:
        if transaction:
            transaction.__exit__(None, None, None)

    results: Dict[str, Any] = {
        "dry_run": dry_run,
        "target_texture_name": target_texture_name,
        "texture_parameter_name": texture_parameter_name,
        "vector_parameter_name": vector_parameter_name,
        "vector_value": list(vector_value),
        "include_static_mesh_default_slot_materials": include_static_mesh_default_slot_materials,
        "static_mesh_component_count": static_mesh_component_count,
        "material_slot_usage_count": material_slot_usage_count,
        "unique_material_asset_count": len(material_records),
        "material_instance_assets_processed": processed_instance_count,
        "matched_material_count": matched_material_count,
        "materials_changed_or_would_change": changed_or_would_change_count,
        "skipped_non_material_instance_count": skipped_non_instance_count,
        "skipped_texture_mismatch_count": skipped_texture_mismatch_count,
        "skipped_missing_texture_parameter_count": skipped_missing_texture_parameter_count,
        "skipped_missing_vector_parameter_count": skipped_missing_vector_parameter_count,
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

    _log(f"Material instance assets processed: {processed_instance_count}")
    _log(f"Materials matching {texture_parameter_name}={target_texture_name}: {matched_material_count}")
    _log(f"Materials {'that would be changed' if dry_run else 'changed'}: {changed_or_would_change_count}")
    _log(f"Skipped texture mismatch: {skipped_texture_mismatch_count}")
    _log(f"Skipped missing texture parameter: {skipped_missing_texture_parameter_count}")
    _log(f"Skipped missing vector parameter: {skipped_missing_vector_parameter_count}")
    _log(f"Errors: {error_count}")

    logged_count = 0
    for operation in operations:
        if operation["status"] not in ("DRY_RUN", "SUCCESS", "ERROR"):
            continue
        if logged_count >= max_log_materials:
            break
        logged_count += 1
        _log(
            f"{operation['status']}: {operation['material_name']} | "
            f"{texture_parameter_name}={operation['texture_name']} | "
            f"{vector_parameter_name} {operation['vector_before']} -> {operation['vector_after']} | "
            f"levels: {operation['levels']}"
        )

    if changed_or_would_change_count > max_log_materials:
        _log(f"...and {changed_or_would_change_count - max_log_materials} more matching material asset(s). See report files for full details.")

    if write_report:
        json_path, csv_path = _write_reports(results, operations, dry_run)
        _log(f"Wrote JSON report: {json_path}")
        _log(f"Wrote CSV report:  {csv_path}")

    if not dry_run and save_dirty_assets:
        _log("Requested save of dirty material assets.")

    _log("White swatch BaseColorScaleTranslation fix complete.")
    return results


if __name__ == "__main__":
    set_white_swatch_base_color_scale_translation_on_open_level_materials(dry_run=True)
