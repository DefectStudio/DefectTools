"""
consolidate_duplicate_materials.py

Unreal Editor Python helper for WBP_06_AssetConsolidator.

Scans loaded levels/sublevels, groups duplicate material assets, chooses the first
material found as the keeper, and replaces duplicate material references with the
keeper. Default mode is DRY RUN.

Active material duplicate signature for this USD cleanup:
- normalized material name / material family name
- parent material
- blend bucket: OPAQUE or MASKED_OR_NON_OPAQUE
- BaseColor vector parameter
- BaseColorTexture texture parameter target name
- OpacityTexture texture parameter target name
- UseBaseColorTexture scalar parameter
- UseOpacityTexture scalar parameter
- Metallic scalar parameter

The normalized material name strips common USD/client import suffixes such as:
- MaterialSG2
- MaterialSG_2
- Material_SG2
- Material_SG_2
- SG2
- SG_2
- _TwoSided

This lets equivalent material copies from separate USD chunks group together
while semantically different materials that share placeholder textures stay apart.
"""
from __future__ import annotations

import csv
import importlib
import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import unreal
import analyze_duplicate_materials

importlib.reload(analyze_duplicate_materials)

LOG_PREFIX = "[AssetConsolidator MaterialConsolidate]"

BASE_COLOR_VECTOR_PARAMETER = "BaseColor"
BASE_COLOR_TEXTURE_PARAMETER = "BaseColorTexture"
OPACITY_TEXTURE_PARAMETER = "OpacityTexture"
USE_BASE_COLOR_TEXTURE_PARAMETER = "UseBaseColorTexture"
USE_OPACITY_TEXTURE_PARAMETER = "UseOpacityTexture"
METALLIC_PARAMETER = "Metallic"


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


# Shared analyzer helpers.
_asset_path = analyze_duplicate_materials._asset_path
_object_name = analyze_duplicate_materials._object_name
_class_name = analyze_duplicate_materials._class_name
_clean_asset_name = analyze_duplicate_materials._clean_asset_name
_get_all_loaded_level_actors = analyze_duplicate_materials._get_all_loaded_level_actors
_get_static_mesh_components = analyze_duplicate_materials._get_static_mesh_components
_component_static_mesh = analyze_duplicate_materials._component_static_mesh
_get_static_materials = analyze_duplicate_materials._get_static_materials
_static_material_interface = analyze_duplicate_materials._static_material_interface
_component_material_count = analyze_duplicate_materials._component_material_count
_component_material = analyze_duplicate_materials._component_material
_get_parent_material = analyze_duplicate_materials._get_parent_material
_blend_mode_bucket = analyze_duplicate_materials._blend_mode_bucket
_texture_name = analyze_duplicate_materials._texture_name
_texture_path = analyze_duplicate_materials._texture_path
_actor_level_info = analyze_duplicate_materials._actor_level_info
_discover_open_world_levels = analyze_duplicate_materials._discover_open_world_levels
_format_level_names = analyze_duplicate_materials._format_level_names
_effective_texture = analyze_duplicate_materials._get_effective_texture_parameter
_direct_scalar_parameter_overrides = analyze_duplicate_materials._direct_scalar_parameter_overrides
_direct_vector_parameter_overrides = analyze_duplicate_materials._direct_vector_parameter_overrides


# ---------------------------------------------------------------------------
# Signature helpers
# ---------------------------------------------------------------------------


def _material_parent_key(material: Any) -> str:
    parent = _get_parent_material(material)
    return _asset_path(parent) if parent else f"<SELF_BASE_MATERIAL>:{_asset_path(material)}"


def _strip_usd_suffixes(name: str) -> str:
    """
    Strip USD/material import suffixes from the end of a lower-case material name.

    Examples:
        colony_simplematerialsg2_twosided      -> colony_simple
        colony_simplematerialsg_2_twosided    -> colony_simple
        colony_simple_material_sg_2_twosided  -> colony_simple
        colony_simple_sg_2_two_sided          -> colony_simple
    """
    suffix_patterns = (
        r"[_-]?two[_-]?sided$",
        r"[_-]?material[_-]?sg[_-]?\d+$",
        r"[_-]?materialsg[_-]?\d+$",
        r"[_-]?sg[_-]?\d+$",
        r"[_-]?copy[_-]?\d*$",
        r"[_-]?duplicate[_-]?\d*$",
        r"[_-]?inst[_-]?\d*$",
    )

    changed = True
    while changed:
        changed = False
        for pattern in suffix_patterns:
            new_name = re.sub(pattern, "", name)
            if new_name != name:
                name = new_name
                changed = True

    return name


def _normalize_material_family_name(material: Any) -> str:
    name = _object_name(material)

    if "." in name:
        name = name.rsplit(".", 1)[-1]
    if "/" in name:
        name = name.rsplit("/", 1)[-1]

    name = name.strip().lower()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"^(mi_|m_)", "", name)

    name = _strip_usd_suffixes(name)

    name = re.sub(r"__+", "_", name)
    name = re.sub(r"--+", "-", name)
    return name.strip("_-") or "<none>"


def _normalize_scalar_value(value: Any) -> str:
    if value is None:
        return "<None>"
    try:
        return f"{round(float(value), 6):.6f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _normalize_vector_value(value: Any) -> str:
    if value is None:
        return "<None>"
    try:
        if isinstance(value, (tuple, list)):
            values = list(value)
        else:
            values = [value.r, value.g, value.b, value.a]
        return "(" + ", ".join(_normalize_scalar_value(item) for item in values[:4]) + ")"
    except Exception:
        return str(value)


def _direct_scalar_value(material: Any, parameter_name: str) -> Optional[float]:
    return _direct_scalar_parameter_overrides(material).get(parameter_name)


def _direct_vector_value(material: Any, parameter_name: str) -> Optional[Tuple[float, float, float, float]]:
    return _direct_vector_parameter_overrides(material).get(parameter_name)


def _get_effective_scalar_parameter(material: Any, parameter_name: str) -> Optional[float]:
    try:
        value = unreal.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(material, parameter_name)
        if value is not None:
            return round(float(value), 6)
    except Exception:
        pass

    current = material
    visited = set()
    while current:
        current_path = _asset_path(current)
        if current_path in visited:
            break
        visited.add(current_path)

        value = _direct_scalar_value(current, parameter_name)
        if value is not None:
            return round(float(value), 6)

        current = _get_parent_material(current)

    return None


def _get_effective_vector_parameter(material: Any, parameter_name: str) -> Optional[Tuple[float, float, float, float]]:
    try:
        value = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material, parameter_name)
        if value is not None:
            return (
                round(float(value.r), 6),
                round(float(value.g), 6),
                round(float(value.b), 6),
                round(float(value.a), 6),
            )
    except Exception:
        pass

    current = material
    visited = set()
    while current:
        current_path = _asset_path(current)
        if current_path in visited:
            break
        visited.add(current_path)

        value = _direct_vector_value(current, parameter_name)
        if value is not None:
            return value

        current = _get_parent_material(current)

    return None


def _material_signature(material: Any) -> Tuple[Any, ...]:
    blend_bucket, _raw_blend = _blend_mode_bucket(material)
    base_texture = _effective_texture(material, BASE_COLOR_TEXTURE_PARAMETER)
    opacity_texture = _effective_texture(material, OPACITY_TEXTURE_PARAMETER)

    return (
        _normalize_material_family_name(material),
        _material_parent_key(material),
        blend_bucket,
        _normalize_vector_value(_get_effective_vector_parameter(material, BASE_COLOR_VECTOR_PARAMETER)),
        _texture_name(base_texture),
        _texture_name(opacity_texture),
        _normalize_scalar_value(_get_effective_scalar_parameter(material, USE_BASE_COLOR_TEXTURE_PARAMETER)),
        _normalize_scalar_value(_get_effective_scalar_parameter(material, USE_OPACITY_TEXTURE_PARAMETER)),
        _normalize_scalar_value(_get_effective_scalar_parameter(material, METALLIC_PARAMETER)),
    )


def _signature_to_dict(signature: Tuple[Any, ...]) -> Dict[str, Any]:
    return {
        "material_family_name": signature[0],
        "parent_material": signature[1],
        "blend_mode_bucket": signature[2],
        "base_color": signature[3],
        "base_color_texture_name": signature[4],
        "opacity_texture_name": signature[5],
        "use_base_color_texture": signature[6],
        "use_opacity_texture": signature[7],
        "metallic": signature[8],
    }


# ---------------------------------------------------------------------------
# Reference helpers
# ---------------------------------------------------------------------------


def _static_material_slot_name(static_material: Any) -> str:
    if not static_material:
        return "<None>"

    for prop_name in ("material_slot_name", "MaterialSlotName", "imported_material_slot_name"):
        try:
            value = static_material.get_editor_property(prop_name)
            if value:
                return str(value)
        except Exception:
            pass

    return "<UnknownSlotName>"


def _static_mesh_slot_material(static_mesh: Any, material_index: int) -> Optional[Any]:
    static_materials = _get_static_materials(static_mesh) if static_mesh else []
    if 0 <= material_index < len(static_materials):
        return _static_material_interface(static_materials[material_index])
    return None


def _component_override_material(component: Any, material_index: int) -> Optional[Any]:
    if not component:
        return None

    for prop_name in ("override_materials", "OverrideMaterials"):
        try:
            overrides = component.get_editor_property(prop_name)
            if overrides and 0 <= material_index < len(overrides) and overrides[material_index]:
                return overrides[material_index]
        except Exception:
            pass

    return None


def _post_edit_changed(obj: Any) -> None:
    if not obj:
        return

    for method_name in ("post_edit_change", "post_edit_change_property"):
        try:
            method = getattr(obj, method_name, None)
            if method:
                method()
                return
        except Exception:
            pass


def _mark_dirty(obj: Any) -> None:
    try:
        obj.mark_package_dirty()
    except Exception:
        pass


def _set_static_mesh_slot_material(static_mesh: Any, material_index: int, keeper_material: Any) -> None:
    static_materials = list(_get_static_materials(static_mesh))

    if material_index < 0 or material_index >= len(static_materials):
        raise IndexError(f"Material slot index {material_index} is out of range.")

    static_mesh.modify()
    static_material = static_materials[material_index]

    try:
        static_material.set_editor_property("material_interface", keeper_material)
    except Exception:
        static_material.material_interface = keeper_material

    static_materials[material_index] = static_material

    try:
        static_mesh.set_editor_property("static_materials", static_materials)
    except Exception:
        pass

    _post_edit_changed(static_mesh)
    _mark_dirty(static_mesh)


def _set_component_material_override(component: Any, material_index: int, keeper_material: Any) -> None:
    component.modify()
    component.set_material(material_index, keeper_material)
    _post_edit_changed(component)
    _mark_dirty(component)


# ---------------------------------------------------------------------------
# Collection / grouping
# ---------------------------------------------------------------------------


def _new_material_record(material: Any, first_seen_index: int) -> Dict[str, Any]:
    parent = _get_parent_material(material)
    blend_bucket, raw_blend = _blend_mode_bucket(material)
    base_texture = _effective_texture(material, BASE_COLOR_TEXTURE_PARAMETER)
    opacity_texture = _effective_texture(material, OPACITY_TEXTURE_PARAMETER)

    return {
        "asset": material,
        "asset_path": _asset_path(material),
        "asset_name": _object_name(material),
        "asset_class": _class_name(material),
        "clean_asset_name": _clean_asset_name(material),
        "material_family_name": _normalize_material_family_name(material),
        "first_seen_index": first_seen_index,
        "parent_material_path": _asset_path(parent),
        "parent_material_name": _clean_asset_name(parent) if parent else "<None>",
        "blend_mode_bucket": blend_bucket,
        "raw_blend_mode": raw_blend,
        "base_color": _normalize_vector_value(_get_effective_vector_parameter(material, BASE_COLOR_VECTOR_PARAMETER)),
        "base_color_texture_name": _texture_name(base_texture),
        "base_color_texture_path": _texture_path(base_texture),
        "opacity_texture_name": _texture_name(opacity_texture),
        "opacity_texture_path": _texture_path(opacity_texture),
        "use_base_color_texture": _normalize_scalar_value(_get_effective_scalar_parameter(material, USE_BASE_COLOR_TEXTURE_PARAMETER)),
        "use_opacity_texture": _normalize_scalar_value(_get_effective_scalar_parameter(material, USE_OPACITY_TEXTURE_PARAMETER)),
        "metallic": _normalize_scalar_value(_get_effective_scalar_parameter(material, METALLIC_PARAMETER)),
        "signature": _material_signature(material),
        "slot_usage_count": 0,
        "levels": set(),
        "level_package_paths": set(),
        "example_actors": [],
        "example_meshes": [],
        "static_mesh_slot_refs": [],
        "component_override_refs": [],
    }


def _ensure_material_record(records: Dict[str, Dict[str, Any]], material: Any, counter: Dict[str, int]) -> Dict[str, Any]:
    material_path = _asset_path(material)
    if material_path not in records:
        records[material_path] = _new_material_record(material, counter["value"])
        counter["value"] += 1
    return records[material_path]


def _add_usage(record: Dict[str, Any], actor_name: str, static_mesh_name: str, level_info: Dict[str, str]) -> None:
    record["slot_usage_count"] += 1
    record["levels"].add(level_info.get("display_name", "<UnknownLevel>"))
    record["level_package_paths"].add(level_info.get("package_path", "<UnknownLevel>"))

    if len(record["example_actors"]) < 10:
        record["example_actors"].append(actor_name)

    if static_mesh_name not in record["example_meshes"] and len(record["example_meshes"]) < 10:
        record["example_meshes"].append(static_mesh_name)


def _collect_material_references() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]], int]:
    actors = _get_all_loaded_level_actors()
    discovered_level_infos = _discover_open_world_levels()

    material_records: Dict[str, Dict[str, Any]] = {}
    level_infos_by_package: Dict[str, Dict[str, str]] = {}
    first_seen_counter = {"value": 0}
    material_slot_usage_count = 0
    seen_static_mesh_slot_keys = set()

    for actor in actors:
        if not actor:
            continue

        actor_name = _object_name(actor)
        actor_path = _asset_path(actor)
        level_info = _actor_level_info(actor)
        level_name = level_info.get("display_name", "<UnknownLevel>")
        level_package_path = level_info.get("package_path", "<UnknownLevel>")
        level_infos_by_package.setdefault(level_package_path, level_info)

        for component in _get_static_mesh_components(actor):
            static_mesh = _component_static_mesh(component)
            if not static_mesh:
                continue

            static_mesh_name = _object_name(static_mesh)
            static_mesh_path = _asset_path(static_mesh)
            component_name = _object_name(component)
            component_path = _asset_path(component)

            for material_index in range(_component_material_count(component)):
                material_slot_usage_count += 1

                override_material = _component_override_material(component, material_index)
                if override_material:
                    record = _ensure_material_record(material_records, override_material, first_seen_counter)
                    _add_usage(record, actor_name, static_mesh_name, level_info)
                    record["component_override_refs"].append(
                        {
                            "actor": actor,
                            "component": component,
                            "material_index": material_index,
                            "actor_name": actor_name,
                            "actor_path": actor_path,
                            "component_name": component_name,
                            "component_path": component_path,
                            "static_mesh_name": static_mesh_name,
                            "static_mesh_path": static_mesh_path,
                            "level_name": level_name,
                            "level_package_path": level_package_path,
                        }
                    )
                    continue

                material = _static_mesh_slot_material(static_mesh, material_index) or _component_material(component, material_index)
                if not material:
                    continue

                record = _ensure_material_record(material_records, material, first_seen_counter)
                _add_usage(record, actor_name, static_mesh_name, level_info)

                static_mesh_slot_key = (static_mesh_path, material_index, _asset_path(material))
                if static_mesh_slot_key in seen_static_mesh_slot_keys:
                    continue

                seen_static_mesh_slot_keys.add(static_mesh_slot_key)
                static_materials = _get_static_materials(static_mesh)
                static_material = static_materials[material_index] if 0 <= material_index < len(static_materials) else None

                record["static_mesh_slot_refs"].append(
                    {
                        "static_mesh": static_mesh,
                        "material_index": material_index,
                        "material_slot_name": _static_material_slot_name(static_material),
                        "static_mesh_name": static_mesh_name,
                        "static_mesh_path": static_mesh_path,
                        "first_actor_name": actor_name,
                        "first_actor_path": actor_path,
                        "first_component_name": component_name,
                        "first_component_path": component_path,
                        "first_level_name": level_name,
                        "first_level_package_path": level_package_path,
                    }
                )

    actor_level_infos = sorted(level_infos_by_package.values(), key=lambda item: item.get("display_name", ""))
    return material_records, actor_level_infos, discovered_level_infos, material_slot_usage_count


def _build_groups(material_records: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_signature: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)

    for record in material_records.values():
        by_signature[record["signature"]].append(record)

    groups = []

    for signature, records in by_signature.items():
        if len(records) < 2:
            continue

        ordered = sorted(records, key=lambda item: int(item["first_seen_index"]))
        keeper = ordered[0]
        duplicates = ordered[1:]

        static_slot_count = sum(len(record["static_mesh_slot_refs"]) for record in duplicates)
        override_count = sum(len(record["component_override_refs"]) for record in duplicates)
        impacted_usage_count = sum(int(record["slot_usage_count"]) for record in duplicates)
        total_usage_count = sum(int(record["slot_usage_count"]) for record in ordered)

        groups.append(
            {
                "signature": signature,
                "signature_info": _signature_to_dict(signature),
                "keeper": keeper,
                "duplicates": duplicates,
                "assets": ordered,
                "asset_count": len(ordered),
                "duplicate_asset_count": len(duplicates),
                "static_mesh_slot_replacement_count": static_slot_count,
                "component_override_replacement_count": override_count,
                "reference_replacement_count": static_slot_count + override_count,
                "impacted_slot_usage_count": impacted_usage_count,
                "total_slot_usage_count": total_usage_count,
            }
        )

    groups.sort(
        key=lambda group: (
            -int(group["impacted_slot_usage_count"]),
            -int(group["reference_replacement_count"]),
            -int(group["asset_count"]),
            str(group["signature_info"].get("material_family_name", "")),
        )
    )

    return groups


# ---------------------------------------------------------------------------
# Consolidation / reporting
# ---------------------------------------------------------------------------


def _operation_record(
    group_index: int,
    reference_type: str,
    action: str,
    status: str,
    keeper: Dict[str, Any],
    duplicate: Dict[str, Any],
    ref: Dict[str, Any],
    error: str = "",
) -> Dict[str, Any]:
    base = {
        "group_index": group_index,
        "reference_type": reference_type,
        "action": action,
        "status": status,
        "error": error,
        "keeper_material_path": keeper["asset_path"],
        "keeper_material_name": keeper["asset_name"],
        "old_material_path": duplicate["asset_path"],
        "old_material_name": duplicate["asset_name"],
        "material_index": ref["material_index"],
        "static_mesh_name": ref["static_mesh_name"],
        "static_mesh_path": ref["static_mesh_path"],
    }

    if reference_type == "STATIC_MESH_SLOT":
        base.update(
            {
                "material_slot_name": ref["material_slot_name"],
                "actor_name": ref["first_actor_name"],
                "actor_path": ref["first_actor_path"],
                "component_name": ref["first_component_name"],
                "component_path": ref["first_component_path"],
                "level_name": ref["first_level_name"],
                "level_package_path": ref["first_level_package_path"],
            }
        )
    else:
        base.update(
            {
                "material_slot_name": "<ComponentOverride>",
                "actor_name": ref["actor_name"],
                "actor_path": ref["actor_path"],
                "component_name": ref["component_name"],
                "component_path": ref["component_path"],
                "level_name": ref["level_name"],
                "level_package_path": ref["level_package_path"],
            }
        )

    return base


def _run_consolidation(groups: Sequence[Dict[str, Any]], dry_run: bool) -> List[Dict[str, Any]]:
    operations: List[Dict[str, Any]] = []
    transaction = None

    if not dry_run:
        transaction = unreal.ScopedEditorTransaction("AssetConsolidator: Consolidate Duplicate Material References")
        transaction.__enter__()

    try:
        for group_index, group in enumerate(groups, start=1):
            keeper = group["keeper"]
            keeper_material = keeper["asset"]

            for duplicate in group["duplicates"]:
                duplicate_path = duplicate["asset_path"]

                for slot_ref in duplicate["static_mesh_slot_refs"]:
                    if dry_run:
                        operations.append(
                            _operation_record(
                                group_index,
                                "STATIC_MESH_SLOT",
                                "WOULD_REPLACE_STATIC_MESH_SLOT_MATERIAL",
                                "DRY_RUN",
                                keeper,
                                duplicate,
                                slot_ref,
                            )
                        )
                        continue

                    try:
                        static_mesh = slot_ref["static_mesh"]
                        material_index = int(slot_ref["material_index"])
                        current_path = _asset_path(_static_mesh_slot_material(static_mesh, material_index))

                        if current_path == keeper["asset_path"]:
                            action, status = "SKIPPED_STATIC_MESH_SLOT_ALREADY_KEEPER", "SKIPPED"
                        else:
                            if current_path != duplicate_path:
                                raise RuntimeError(f"Current slot material is {current_path}; expected {duplicate_path}.")

                            _set_static_mesh_slot_material(static_mesh, material_index, keeper_material)
                            action, status = "REPLACED_STATIC_MESH_SLOT_MATERIAL", "SUCCESS"

                        operations.append(_operation_record(group_index, "STATIC_MESH_SLOT", action, status, keeper, duplicate, slot_ref))
                    except Exception as exc:
                        operations.append(
                            _operation_record(
                                group_index,
                                "STATIC_MESH_SLOT",
                                "REPLACE_STATIC_MESH_SLOT_MATERIAL_FAILED",
                                "ERROR",
                                keeper,
                                duplicate,
                                slot_ref,
                                str(exc),
                            )
                        )

                for override_ref in duplicate["component_override_refs"]:
                    if dry_run:
                        operations.append(
                            _operation_record(
                                group_index,
                                "COMPONENT_OVERRIDE",
                                "WOULD_REPLACE_COMPONENT_MATERIAL_OVERRIDE",
                                "DRY_RUN",
                                keeper,
                                duplicate,
                                override_ref,
                            )
                        )
                        continue

                    try:
                        actor = override_ref["actor"]
                        component = override_ref["component"]
                        material_index = int(override_ref["material_index"])
                        current_path = _asset_path(_component_override_material(component, material_index))

                        if current_path == keeper["asset_path"]:
                            action, status = "SKIPPED_COMPONENT_OVERRIDE_ALREADY_KEEPER", "SKIPPED"
                        else:
                            if current_path != duplicate_path:
                                raise RuntimeError(f"Current override material is {current_path}; expected {duplicate_path}.")

                            if actor:
                                actor.modify()

                            _set_component_material_override(component, material_index, keeper_material)

                            if actor:
                                _post_edit_changed(actor)
                                _mark_dirty(actor)

                            action, status = "REPLACED_COMPONENT_MATERIAL_OVERRIDE", "SUCCESS"

                        operations.append(_operation_record(group_index, "COMPONENT_OVERRIDE", action, status, keeper, duplicate, override_ref))
                    except Exception as exc:
                        operations.append(
                            _operation_record(
                                group_index,
                                "COMPONENT_OVERRIDE",
                                "REPLACE_COMPONENT_MATERIAL_OVERRIDE_FAILED",
                                "ERROR",
                                keeper,
                                duplicate,
                                override_ref,
                                str(exc),
                            )
                        )
    finally:
        if transaction:
            transaction.__exit__(None, None, None)

    if not dry_run:
        try:
            unreal.EditorLevelLibrary.redraw_all_viewports()
        except Exception:
            pass

    return operations


def _json_safe_asset(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_path": record["asset_path"],
        "asset_name": record["asset_name"],
        "asset_class": record["asset_class"],
        "material_family_name": record["material_family_name"],
        "first_seen_index": record["first_seen_index"],
        "slot_usage_count": record["slot_usage_count"],
        "levels": sorted(record["levels"]),
        "level_package_paths": sorted(record["level_package_paths"]),
        "parent_material_path": record["parent_material_path"],
        "blend_mode_bucket": record["blend_mode_bucket"],
        "raw_blend_mode": record["raw_blend_mode"],
        "base_color": record["base_color"],
        "base_color_texture_name": record["base_color_texture_name"],
        "base_color_texture_path": record["base_color_texture_path"],
        "opacity_texture_name": record["opacity_texture_name"],
        "opacity_texture_path": record["opacity_texture_path"],
        "use_base_color_texture": record["use_base_color_texture"],
        "use_opacity_texture": record["use_opacity_texture"],
        "metallic": record["metallic"],
        "example_actors": list(record["example_actors"]),
        "example_meshes": list(record["example_meshes"]),
        "static_mesh_slot_reference_count": len(record["static_mesh_slot_refs"]),
        "component_override_reference_count": len(record["component_override_refs"]),
    }


def _json_safe_group(group: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "signature_info": group["signature_info"],
        "asset_count": group["asset_count"],
        "duplicate_asset_count": group["duplicate_asset_count"],
        "total_slot_usage_count": group["total_slot_usage_count"],
        "impacted_slot_usage_count": group["impacted_slot_usage_count"],
        "static_mesh_slot_replacement_count": group["static_mesh_slot_replacement_count"],
        "component_override_replacement_count": group["component_override_replacement_count"],
        "reference_replacement_count": group["reference_replacement_count"],
        "keeper": _json_safe_asset(group["keeper"]),
        "duplicates": [_json_safe_asset(record) for record in group["duplicates"]],
    }


def _write_reports(report: Dict[str, Any], dry_run: bool) -> Tuple[str, str]:
    output_dir = os.path.join(unreal.Paths.project_saved_dir(), "AssetConsolidator")
    os.makedirs(output_dir, exist_ok=True)

    suffix = "dry_run" if dry_run else "executed"
    json_path = os.path.join(output_dir, f"duplicate_material_consolidation_{suffix}.json")
    csv_path = os.path.join(output_dir, f"duplicate_material_consolidation_{suffix}.csv")

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
                "reference_type",
                "level_name",
                "actor_name",
                "component_name",
                "static_mesh_name",
                "material_index",
                "material_slot_name",
                "old_material_path",
                "keeper_material_path",
                "component_path",
                "actor_path",
                "static_mesh_path",
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
                    operation["reference_type"],
                    operation["level_name"],
                    operation["actor_name"],
                    operation["component_name"],
                    operation["static_mesh_name"],
                    operation["material_index"],
                    operation["material_slot_name"],
                    operation["old_material_path"],
                    operation["keeper_material_path"],
                    operation["component_path"],
                    operation["actor_path"],
                    operation["static_mesh_path"],
                    operation["level_package_path"],
                ]
            )

    return json_path, csv_path


def _log_group_summary(groups: Sequence[Dict[str, Any]], max_log_groups: int, max_assets_per_group_log: int) -> None:
    if not groups:
        _log("No duplicate material candidates found. Nothing to consolidate.")
        return

    _log(f"Duplicate material consolidation groups: {len(groups)}")

    for group_index, group in enumerate(groups[:max_log_groups], start=1):
        signature = group["signature_info"]
        keeper = group["keeper"]

        _log(
            f"Group {group_index}: keeper={keeper['asset_name']} | family={signature['material_family_name']} | "
            f"{group['duplicate_asset_count']} duplicate material asset(s), "
            f"{group['reference_replacement_count']} reference(s) to replace "
            f"({group['static_mesh_slot_replacement_count']} static mesh slot(s), "
            f"{group['component_override_replacement_count']} component override(s)); "
            f"{group['impacted_slot_usage_count']} slot usage(s) impacted"
        )

        _log(
            "  Signature: "
            f"MaterialName={signature['material_family_name']} | Parent={signature['parent_material']} | "
            f"Blend={signature['blend_mode_bucket']} | BaseColor={signature['base_color']} | "
            f"BaseColorTexture={signature['base_color_texture_name']} | "
            f"OpacityTexture={signature['opacity_texture_name']} | "
            f"UseBaseColorTexture={signature['use_base_color_texture']} | "
            f"UseOpacityTexture={signature['use_opacity_texture']} | Metallic={signature['metallic']}"
        )

        _log(
            f"  Keeper: {keeper['asset_path']} "
            f"(first seen; {keeper['slot_usage_count']} slot usage(s); levels: {', '.join(sorted(keeper['levels']))})"
        )

        for duplicate in group["duplicates"][:max_assets_per_group_log]:
            _log(
                f"    Duplicate: {duplicate['asset_path']} "
                f"({duplicate['slot_usage_count']} slot usage(s); "
                f"{len(duplicate['static_mesh_slot_refs'])} static mesh slot ref(s); "
                f"{len(duplicate['component_override_refs'])} component override(s); "
                f"levels: {', '.join(sorted(duplicate['levels']))})"
            )

        remaining = len(group["duplicates"]) - max_assets_per_group_log
        if remaining > 0:
            _log(f"    ...and {remaining} more duplicate material asset(s) in this group.")

    remaining_groups = len(groups) - max_log_groups
    if remaining_groups > 0:
        _log(f"...and {remaining_groups} more group(s). See report files for full details.")


def _save_dirty_packages(save_dirty_levels: bool, save_dirty_assets: bool, dry_run: bool) -> None:
    if dry_run or (not save_dirty_levels and not save_dirty_assets):
        return

    try:
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(
            save_map_packages=bool(save_dirty_levels),
            save_content_packages=bool(save_dirty_assets),
        )
        _log(f"Requested save of dirty packages (maps={bool(save_dirty_levels)}, assets={bool(save_dirty_assets)}).")
    except TypeError:
        try:
            unreal.EditorLoadingAndSavingUtils.save_dirty_packages(bool(save_dirty_levels), bool(save_dirty_assets))
            _log(f"Requested save of dirty packages (maps={bool(save_dirty_levels)}, assets={bool(save_dirty_assets)}).")
        except Exception as exc:
            _warn(f"Could not save dirty packages automatically: {exc}")
    except Exception as exc:
        _warn(f"Could not save dirty packages automatically: {exc}")


def consolidate_duplicate_materials(
    dry_run: bool = True,
    write_report: bool = True,
    save_dirty_levels: bool = False,
    save_dirty_assets: bool = False,
    include_extra_parameter_overrides: bool = False,
    max_log_groups: int = 25,
    max_assets_per_group_log: int = 10,
) -> Dict[str, Any]:
    """Consolidate duplicate material references in the currently loaded levels."""
    mode_label = "DRY RUN" if dry_run else "EXECUTE"
    _log(f"Starting duplicate material consolidation. Mode: {mode_label}")

    if include_extra_parameter_overrides:
        _warn("include_extra_parameter_overrides=True was passed, but this version uses only the named USD signature fields.")

    material_records, actor_levels, open_world_levels, material_slot_usage_count = _collect_material_references()
    groups = _build_groups(material_records)

    duplicate_candidate_asset_count = sum(group["asset_count"] for group in groups)
    duplicate_asset_replacement_count = sum(group["duplicate_asset_count"] for group in groups)
    static_mesh_slot_replacement_count = sum(group["static_mesh_slot_replacement_count"] for group in groups)
    component_override_replacement_count = sum(group["component_override_replacement_count"] for group in groups)
    reference_replacement_count = sum(group["reference_replacement_count"] for group in groups)
    impacted_slot_usage_count = sum(group["impacted_slot_usage_count"] for group in groups)

    _log("Scan complete.")
    _log(f"Open world levels discovered: {len(open_world_levels)} - {_format_level_names(open_world_levels)}")
    _log(f"Actor level packages scanned: {len(actor_levels)} - {_format_level_names(actor_levels)}")
    _log(f"Material slot usages scanned: {material_slot_usage_count}")
    _log(f"Unique material assets found: {len(material_records)}")
    _log("Signature fields: Material name, Parent material, Blend mode, BaseColor, BaseColorTexture, OpacityTexture, UseBaseColorTexture, UseOpacityTexture, Metallic")
    _log("Material name normalization: strips MaterialSG0, MaterialSG_0, Material_SG0, Material_SG_0, SG0, SG_0, and TwoSided suffixes")
    _log(f"Duplicate candidate groups: {len(groups)}")
    _log(f"Duplicate candidate material assets: {duplicate_candidate_asset_count}")
    _log(f"Duplicate material assets that would be replaced: {duplicate_asset_replacement_count}")
    _log(f"Static Mesh asset slot references that would be changed: {static_mesh_slot_replacement_count}")
    _log(f"Component material override references that would be changed: {component_override_replacement_count}")
    _log(f"Total material references that would be changed: {reference_replacement_count}")
    _log(f"Estimated material slot usages impacted: {impacted_slot_usage_count}")

    _log_group_summary(groups, max_log_groups, max_assets_per_group_log)

    operations = _run_consolidation(groups, dry_run=dry_run)
    dry_run_count = sum(1 for operation in operations if operation["status"] == "DRY_RUN")
    success_count = sum(1 for operation in operations if operation["status"] == "SUCCESS")
    skipped_count = sum(1 for operation in operations if operation["status"] == "SKIPPED")
    error_count = sum(1 for operation in operations if operation["status"] == "ERROR")

    _save_dirty_packages(save_dirty_levels, save_dirty_assets, dry_run)

    signature_fields = [
        "material_family_name",
        "parent_material",
        "blend_mode_bucket",
        "base_color",
        "base_color_texture_name",
        "opacity_texture_name",
        "use_base_color_texture",
        "use_opacity_texture",
        "metallic",
    ]

    report = {
        "summary": {
            "mode": mode_label,
            "dry_run": dry_run,
            "actor_level_count": len(actor_levels),
            "actor_levels_scanned": [info["display_name"] for info in actor_levels],
            "actor_level_details": actor_levels,
            "open_world_level_count": len(open_world_levels),
            "open_world_levels_detected": [info["display_name"] for info in open_world_levels],
            "open_world_level_details": open_world_levels,
            "material_slot_usages_scanned": material_slot_usage_count,
            "unique_material_asset_count": len(material_records),
            "duplicate_group_count": len(groups),
            "duplicate_candidate_asset_count": duplicate_candidate_asset_count,
            "duplicate_asset_replacement_count": duplicate_asset_replacement_count,
            "static_mesh_slot_reference_replacement_count": static_mesh_slot_replacement_count,
            "component_override_reference_replacement_count": component_override_replacement_count,
            "material_reference_replacement_count": reference_replacement_count,
            "impacted_slot_usage_count": impacted_slot_usage_count,
            "operation_count": len(operations),
            "dry_run_operation_count": dry_run_count,
            "successful_operation_count": success_count,
            "skipped_operation_count": skipped_count,
            "error_count": error_count,
            "save_dirty_levels_requested": bool(save_dirty_levels),
            "save_dirty_assets_requested": bool(save_dirty_assets),
            "include_extra_parameter_overrides": bool(include_extra_parameter_overrides),
            "signature_fields": signature_fields,
        },
        "consolidation_groups": [_json_safe_group(group) for group in groups],
        "operations": operations,
    }

    if write_report:
        json_path, csv_path = _write_reports(report, dry_run)
        _log(f"Wrote JSON report: {json_path}")
        _log(f"Wrote CSV report:  {csv_path}")

    if dry_run:
        _log(f"Dry run complete. {dry_run_count} material reference(s) would be replaced.")
    elif error_count:
        _warn(f"Consolidation complete with {error_count} error(s). Successful replacements: {success_count}; skipped: {skipped_count}")
    else:
        _log(f"Consolidation complete. Successful replacements: {success_count}; skipped: {skipped_count}")

    return report


if __name__ == "__main__":
    consolidate_duplicate_materials(dry_run=True)
