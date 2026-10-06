"""
analyze_duplicate_materials.py

Unreal Editor Python helper for WBP_06_AssetConsolidator.

Scans all currently loaded actors in the open level and loaded/open sublevels,
collects materials used by StaticMeshComponent material slots, and reports
material duplicate candidates.

Requested comparison keys:
- parent material
- effective Blend Mode bucket: OPAQUE or MASKED_OR_NON_OPAQUE
- BaseColorTexture parameter target texture name
- OpacityTexture parameter target texture name

For safer future consolidation, this script also includes direct texture/scalar/
vector parameter override signatures by default. This helps avoid grouping two
material instances that share BaseColorTexture and OpacityTexture but differ in
roughness, tint, normal, ORM, or other overridden parameters.

This is an analysis/dry-run report only. It does not modify assets or levels.
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

import unreal


LOG_PREFIX = "[AssetConsolidator MaterialAnalyze]"

BASE_COLOR_PARAMETER = "BaseColorTexture"
OPACITY_PARAMETER = "OpacityTexture"


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _error(message: str) -> None:
    unreal.log_error(f"{LOG_PREFIX} {message}")


def _asset_path(asset: Any) -> str:
    if not asset:
        return "<None>"
    try:
        return asset.get_path_name()
    except Exception:
        return str(asset)


def _object_name(obj: Any) -> str:
    if not obj:
        return "<None>"
    try:
        return obj.get_name()
    except Exception:
        path = _asset_path(obj)
        if "." in path:
            return path.rsplit(".", 1)[-1]
        return path.rsplit("/", 1)[-1]


def _class_name(obj: Any) -> str:
    if not obj:
        return "<None>"
    try:
        return obj.get_class().get_name()
    except Exception:
        return type(obj).__name__


def _clean_asset_name(name_or_asset: Any) -> str:
    if not isinstance(name_or_asset, str):
        name = _object_name(name_or_asset)
    else:
        name = name_or_asset

    if "." in name:
        name = name.rsplit(".", 1)[-1]
    if "/" in name:
        name = name.rsplit("/", 1)[-1]

    name = name.strip().lower()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"__+", "_", name)

    changed = True
    while changed:
        changed = False
        for pattern in (r"(_copy\d*)$", r"(_duplicate\d*)$", r"(_inst\d*)$", r"(_\d+)$"):
            new_name = re.sub(pattern, "", name)
            if new_name != name:
                name = new_name
                changed = True

    return name.strip("_")


# ---------------------------------------------------------------------------
# Level reporting helpers
# ---------------------------------------------------------------------------
#
# Unreal ULevel objects are often named "PersistentLevel" even when the actor is
# in a sublevel. The useful sublevel name is usually the ULevel outer package:
# /Game/.../LVL_RelayAGeoA_v003. These helpers report that package asset name
# instead of the ULevel object name, so the analysis can confirm which sublevels
# were actually scanned.


def _package_path(obj: Any) -> str:
    if not obj:
        return "<None>"

    try:
        outermost = obj.get_outermost()
        if outermost:
            name = outermost.get_name()
            if name:
                return str(name)
    except Exception:
        pass

    try:
        path = obj.get_path_name()
        if path:
            return str(path).split(":", 1)[0].split(".", 1)[0]
    except Exception:
        pass

    return "<None>"


def _display_name_from_package_path(package_path: str, fallback: str = "<UnknownLevel>") -> str:
    if not package_path or package_path in ("<None>", "/Engine/Transient"):
        return fallback

    clean = package_path.split(":", 1)[0].split(".", 1)[0].strip()
    if not clean:
        return fallback

    return clean.rsplit("/", 1)[-1] or fallback


def _level_info_from_level(level: Any) -> Dict[str, str]:
    object_name = _object_name(level)
    package_path = _package_path(level)
    display_name = _display_name_from_package_path(package_path, object_name)

    return {
        "display_name": display_name,
        "package_path": package_path,
        "ulevel_object_name": object_name,
        "class_name": _class_name(level),
    }


def _level_info_from_streaming_level(streaming_level: Any) -> Optional[Dict[str, str]]:
    if not streaming_level:
        return None

    loaded_level = None
    try:
        loaded_level = streaming_level.get_loaded_level()
    except Exception:
        loaded_level = None

    if loaded_level:
        info = _level_info_from_level(loaded_level)
        info["streaming_level_name"] = _object_name(streaming_level)
        info["is_loaded"] = "True"
        return info

    package_path = ""
    for attr_name in ("get_world_asset_package_name", "get_package_name"):
        try:
            attr = getattr(streaming_level, attr_name, None)
            if attr:
                package_path = str(attr())
                if package_path:
                    break
        except Exception:
            pass

    if not package_path:
        for prop_name in ("world_asset", "package_name_to_load"):
            try:
                value = streaming_level.get_editor_property(prop_name)
                if value:
                    package_path = _package_path(value) if not isinstance(value, str) else value
                    if package_path:
                        break
            except Exception:
                pass

    if not package_path:
        return {
            "display_name": _object_name(streaming_level),
            "package_path": "<UnknownStreamingLevelPackage>",
            "ulevel_object_name": "<NotLoaded>",
            "class_name": _class_name(streaming_level),
            "streaming_level_name": _object_name(streaming_level),
            "is_loaded": "False",
        }

    return {
        "display_name": _display_name_from_package_path(package_path, _object_name(streaming_level)),
        "package_path": package_path,
        "ulevel_object_name": "<NotLoaded>",
        "class_name": _class_name(streaming_level),
        "streaming_level_name": _object_name(streaming_level),
        "is_loaded": "False",
    }


def _dedupe_level_infos(level_infos: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    deduped: Dict[str, Dict[str, str]] = {}

    for info in level_infos:
        if not info:
            continue
        key = info.get("package_path") or info.get("display_name") or "<UnknownLevel>"
        if key not in deduped:
            deduped[key] = dict(info)
            continue

        existing = deduped[key]
        if existing.get("ulevel_object_name") == "<NotLoaded>" and info.get("ulevel_object_name") != "<NotLoaded>":
            deduped[key] = dict(info)

    return sorted(deduped.values(), key=lambda item: item.get("display_name", ""))


def _get_editor_world() -> Optional[Any]:
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        pass

    try:
        subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if subsystem:
            return subsystem.get_editor_world()
    except Exception:
        pass

    return None


def _discover_open_world_levels() -> List[Dict[str, str]]:
    """Best-effort list of level assets visible to the open editor world."""
    world = _get_editor_world()
    if not world:
        return []

    level_infos: List[Dict[str, str]] = []

    try:
        persistent_level = world.get_persistent_level()
        if persistent_level:
            level_infos.append(_level_info_from_level(persistent_level))
    except Exception:
        pass

    try:
        for level in world.get_levels() or []:
            level_infos.append(_level_info_from_level(level))
    except Exception:
        pass

    try:
        for streaming_level in world.get_streaming_levels() or []:
            info = _level_info_from_streaming_level(streaming_level)
            if info:
                level_infos.append(info)
    except Exception:
        pass

    return _dedupe_level_infos(level_infos)


def _actor_level_info(actor: Any) -> Dict[str, str]:
    for getter_name in ("get_level", "get_outer"):
        try:
            getter = getattr(actor, getter_name, None)
            level = getter() if getter else None
            if level:
                return _level_info_from_level(level)
        except Exception:
            pass

    return {
        "display_name": "<UnknownLevel>",
        "package_path": "<UnknownLevel>",
        "ulevel_object_name": "<UnknownLevel>",
        "class_name": "<Unknown>",
    }


def _format_level_names(level_infos: Sequence[Dict[str, str]]) -> str:
    names = [info.get("display_name", "<UnknownLevel>") for info in level_infos]
    return ", ".join(names) if names else "<None>"


def _get_all_loaded_level_actors() -> List[Any]:
    """Returns actors from the persistent level and any loaded/open sublevels."""
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem:
            return list(subsystem.get_all_level_actors())
    except Exception as exc:
        _warn(f"EditorActorSubsystem actor query failed; trying EditorLevelLibrary. Error: {exc}")

    try:
        return list(unreal.EditorLevelLibrary.get_all_level_actors())
    except Exception as exc:
        _error(f"Could not query loaded level actors: {exc}")
        return []


def _get_static_mesh_components(actor: Any) -> List[Any]:
    components: List[Any] = []
    seen_paths = set()

    classes_to_try = []
    for class_name in (
        "StaticMeshComponent",
        "InstancedStaticMeshComponent",
        "HierarchicalInstancedStaticMeshComponent",
    ):
        cls = getattr(unreal, class_name, None)
        if cls:
            classes_to_try.append(cls)

    for cls in classes_to_try:
        try:
            found = actor.get_components_by_class(cls)
        except Exception:
            found = []

        for component in found:
            path = _asset_path(component)
            if path not in seen_paths:
                seen_paths.add(path)
                components.append(component)

    return components


def _component_static_mesh(component: Any) -> Optional[Any]:
    for prop_name in ("static_mesh", "StaticMesh"):
        try:
            value = component.get_editor_property(prop_name)
            if value:
                return value
        except Exception:
            pass

    try:
        return component.static_mesh
    except Exception:
        return None


def _get_static_materials(static_mesh: Any) -> List[Any]:
    try:
        static_materials = static_mesh.get_editor_property("static_materials")
        return list(static_materials) if static_materials else []
    except Exception:
        pass

    try:
        return list(static_mesh.static_materials)
    except Exception:
        return []


def _static_material_interface(static_material: Any) -> Optional[Any]:
    for prop_name in ("material_interface", "MaterialInterface"):
        try:
            material = static_material.get_editor_property(prop_name)
            if material:
                return material
        except Exception:
            pass

    try:
        return static_material.material_interface
    except Exception:
        return None


def _component_material_count(component: Any) -> int:
    try:
        return int(component.get_num_materials())
    except Exception:
        pass

    static_mesh = _component_static_mesh(component)
    if static_mesh:
        return len(_get_static_materials(static_mesh))

    return 0


def _component_material(component: Any, material_index: int) -> Optional[Any]:
    try:
        material = component.get_material(material_index)
        if material:
            return material
    except Exception:
        pass

    static_mesh = _component_static_mesh(component)
    if not static_mesh:
        return None

    static_materials = _get_static_materials(static_mesh)
    if 0 <= material_index < len(static_materials):
        return _static_material_interface(static_materials[material_index])

    return None


def _get_parent_material(material: Any) -> Optional[Any]:
    if not material:
        return None

    try:
        return material.get_editor_property("parent")
    except Exception:
        return None


def _material_parent_key(material: Any) -> str:
    parent = _get_parent_material(material)
    if parent:
        return _asset_path(parent)

    # Base Material assets do not have parents. Keep them separate by their own path.
    return f"<SELF_BASE_MATERIAL>:{_asset_path(material)}"


def _enum_to_string(value: Any) -> str:
    if value is None:
        return "<None>"

    name = getattr(value, "name", None)
    if name:
        return str(name)

    return str(value)


def _get_direct_blend_mode(material: Any) -> Optional[Any]:
    if not material:
        return None

    try:
        return material.get_blend_mode()
    except Exception:
        pass

    try:
        return material.get_editor_property("blend_mode")
    except Exception:
        pass

    try:
        base_overrides = material.get_editor_property("base_property_overrides")
        if base_overrides:
            try:
                override_blend_mode = bool(base_overrides.get_editor_property("override_blend_mode"))
            except Exception:
                override_blend_mode = False

            if override_blend_mode:
                try:
                    return base_overrides.get_editor_property("blend_mode")
                except Exception:
                    pass
    except Exception:
        pass

    return None


def _get_effective_blend_mode(material: Any) -> Optional[Any]:
    current = material
    visited = set()

    while current:
        current_path = _asset_path(current)
        if current_path in visited:
            break
        visited.add(current_path)

        blend_mode = _get_direct_blend_mode(current)
        if blend_mode is not None:
            return blend_mode

        current = _get_parent_material(current)

    return None


def _blend_mode_bucket(material: Any) -> Tuple[str, str]:
    blend_mode = _get_effective_blend_mode(material)
    raw = _enum_to_string(blend_mode)
    raw_upper = raw.upper()

    if raw_upper.endswith("BLEND_OPAQUE") or raw_upper.endswith("OPAQUE"):
        return "OPAQUE", raw

    # User-facing bucket for this environment pipeline: every non-opaque USD
    # material is treated as the masked/decal-style group.
    return "MASKED_OR_NON_OPAQUE", raw


def _parameter_info_name(parameter_value: Any) -> str:
    try:
        parameter_info = parameter_value.get_editor_property("parameter_info")
        try:
            name = parameter_info.get_editor_property("name")
        except Exception:
            name = getattr(parameter_info, "name", None)
        if name:
            return str(name)
    except Exception:
        pass

    for prop_name in ("parameter_name", "name"):
        try:
            value = parameter_value.get_editor_property(prop_name)
            if value:
                return str(value)
        except Exception:
            pass

    return "<UnknownParameter>"


def _parameter_asset_value(parameter_value: Any) -> Optional[Any]:
    for prop_name in ("parameter_value", "texture", "value"):
        try:
            value = parameter_value.get_editor_property(prop_name)
            if value:
                return value
        except Exception:
            pass
    return None


def _parameter_scalar_value(parameter_value: Any) -> Optional[float]:
    for prop_name in ("parameter_value", "value"):
        try:
            value = parameter_value.get_editor_property(prop_name)
            if value is not None:
                return round(float(value), 6)
        except Exception:
            pass
    return None


def _parameter_vector_value(parameter_value: Any) -> Optional[Tuple[float, float, float, float]]:
    for prop_name in ("parameter_value", "value"):
        try:
            value = parameter_value.get_editor_property(prop_name)
        except Exception:
            continue

        if value is None:
            continue

        try:
            return (
                round(float(value.r), 6),
                round(float(value.g), 6),
                round(float(value.b), 6),
                round(float(value.a), 6),
            )
        except Exception:
            pass

    return None


def _direct_texture_parameter_overrides(material: Any) -> Dict[str, Optional[Any]]:
    overrides: Dict[str, Optional[Any]] = {}

    try:
        values = material.get_editor_property("texture_parameter_values")
    except Exception:
        values = []

    for parameter_value in values or []:
        overrides[_parameter_info_name(parameter_value)] = _parameter_asset_value(parameter_value)

    return overrides


def _direct_scalar_parameter_overrides(material: Any) -> Dict[str, Optional[float]]:
    overrides: Dict[str, Optional[float]] = {}

    try:
        values = material.get_editor_property("scalar_parameter_values")
    except Exception:
        values = []

    for parameter_value in values or []:
        overrides[_parameter_info_name(parameter_value)] = _parameter_scalar_value(parameter_value)

    return overrides


def _direct_vector_parameter_overrides(material: Any) -> Dict[str, Optional[Tuple[float, float, float, float]]]:
    overrides: Dict[str, Optional[Tuple[float, float, float, float]]] = {}

    try:
        values = material.get_editor_property("vector_parameter_values")
    except Exception:
        values = []

    for parameter_value in values or []:
        overrides[_parameter_info_name(parameter_value)] = _parameter_vector_value(parameter_value)

    return overrides


def _get_effective_texture_parameter(material: Any, parameter_name: str) -> Optional[Any]:
    # Preferred path for material instances when available.
    try:
        value = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, parameter_name)
        if value:
            return value
    except Exception:
        pass

    # Direct override or parent-chain fallback.
    current = material
    visited = set()

    while current:
        current_path = _asset_path(current)
        if current_path in visited:
            break
        visited.add(current_path)

        overrides = _direct_texture_parameter_overrides(current)
        if parameter_name in overrides:
            return overrides[parameter_name]

        current = _get_parent_material(current)

    return None


def _texture_name(texture: Optional[Any]) -> str:
    if not texture:
        return "<None>"
    return _clean_asset_name(texture)


def _texture_path(texture: Optional[Any]) -> str:
    if not texture:
        return "<None>"
    return _asset_path(texture)


def _texture_override_signature(material: Any) -> Tuple[Tuple[str, str], ...]:
    overrides = _direct_texture_parameter_overrides(material)
    return tuple(sorted((name, _texture_name(texture)) for name, texture in overrides.items()))


def _scalar_override_signature(material: Any) -> Tuple[Tuple[str, Optional[float]], ...]:
    overrides = _direct_scalar_parameter_overrides(material)
    return tuple(sorted(overrides.items()))


def _vector_override_signature(material: Any) -> Tuple[Tuple[str, Optional[Tuple[float, float, float, float]]], ...]:
    overrides = _direct_vector_parameter_overrides(material)
    return tuple(sorted(overrides.items()))


def _material_signature(material: Any, include_extra_parameter_overrides: bool) -> Tuple[Any, ...]:
    parent_key = _material_parent_key(material)
    blend_bucket, raw_blend_mode = _blend_mode_bucket(material)

    base_color_texture = _get_effective_texture_parameter(material, BASE_COLOR_PARAMETER)
    opacity_texture = _get_effective_texture_parameter(material, OPACITY_PARAMETER)

    signature = [
        parent_key,
        blend_bucket,
        _texture_name(base_color_texture),
        _texture_name(opacity_texture),
    ]

    if include_extra_parameter_overrides:
        signature.extend(
            [
                _texture_override_signature(material),
                _scalar_override_signature(material),
                _vector_override_signature(material),
            ]
        )

    return tuple(signature)


def _signature_to_dict(signature: Tuple[Any, ...], include_extra_parameter_overrides: bool) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "parent_material": signature[0],
        "blend_mode_bucket": signature[1],
        "base_color_texture_name": signature[2],
        "opacity_texture_name": signature[3],
    }

    if include_extra_parameter_overrides:
        data["direct_texture_parameter_overrides"] = [list(item) for item in signature[4]]
        data["direct_scalar_parameter_overrides"] = [list(item) for item in signature[5]]
        data["direct_vector_parameter_overrides"] = [list(item) for item in signature[6]]

    return data


def _collect_material_usage(
    include_extra_parameter_overrides: bool,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]], int]:
    actors = _get_all_loaded_level_actors()
    discovered_level_infos = _discover_open_world_levels()

    material_records: Dict[str, Dict[str, Any]] = {}
    actor_level_infos_by_package: Dict[str, Dict[str, str]] = {}
    material_slot_count = 0

    for actor in actors:
        if not actor:
            continue

        actor_name = _object_name(actor)
        level_info = _actor_level_info(actor)
        level_name = level_info["display_name"]
        level_key = level_info.get("package_path") or level_name
        actor_level_infos_by_package.setdefault(level_key, level_info)

        for component in _get_static_mesh_components(actor):
            static_mesh = _component_static_mesh(component)
            static_mesh_name = _object_name(static_mesh) if static_mesh else "<NoStaticMesh>"
            component_path = _asset_path(component)
            slot_count = _component_material_count(component)

            for material_index in range(slot_count):
                material = _component_material(component, material_index)
                if not material:
                    continue

                material_slot_count += 1
                material_path = _asset_path(material)

                if material_path not in material_records:
                    parent = _get_parent_material(material)
                    blend_bucket, raw_blend_mode = _blend_mode_bucket(material)
                    base_color_texture = _get_effective_texture_parameter(material, BASE_COLOR_PARAMETER)
                    opacity_texture = _get_effective_texture_parameter(material, OPACITY_PARAMETER)

                    material_records[material_path] = {
                        "asset": material,
                        "asset_path": material_path,
                        "asset_name": _object_name(material),
                        "clean_asset_name": _clean_asset_name(material),
                        "asset_class": _class_name(material),
                        "parent_material_path": _asset_path(parent),
                        "parent_material_name": _clean_asset_name(parent) if parent else "<None>",
                        "blend_mode_bucket": blend_bucket,
                        "raw_blend_mode": raw_blend_mode,
                        "base_color_texture_name": _texture_name(base_color_texture),
                        "base_color_texture_path": _texture_path(base_color_texture),
                        "opacity_texture_name": _texture_name(opacity_texture),
                        "opacity_texture_path": _texture_path(opacity_texture),
                        "signature": _material_signature(material, include_extra_parameter_overrides),
                        "slot_usage_count": 0,
                        "levels": set(),
                        "level_package_paths": set(),
                        "example_actors": [],
                        "example_meshes": [],
                        "component_slots": [],
                    }

                record = material_records[material_path]
                record["slot_usage_count"] += 1
                record["levels"].add(level_name)
                record["level_package_paths"].add(level_info.get("package_path", "<UnknownLevel>"))

                if len(record["example_actors"]) < 10:
                    record["example_actors"].append(actor_name)

                if static_mesh_name not in record["example_meshes"] and len(record["example_meshes"]) < 10:
                    record["example_meshes"].append(static_mesh_name)

                if len(record["component_slots"]) < 10:
                    record["component_slots"].append(
                        {
                            "component_path": component_path,
                            "material_index": material_index,
                            "actor_name": actor_name,
                            "static_mesh_name": static_mesh_name,
                            "level_name": level_name,
                            "level_package_path": level_info.get("package_path", "<UnknownLevel>"),
                        }
                    )

    actor_level_infos = sorted(
        actor_level_infos_by_package.values(),
        key=lambda item: item.get("display_name", ""),
    )

    return material_records, actor_level_infos, discovered_level_infos, material_slot_count


def _build_duplicate_groups(
    material_records: Dict[str, Dict[str, Any]],
    include_extra_parameter_overrides: bool,
) -> List[Dict[str, Any]]:
    signature_groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)

    for record in material_records.values():
        signature_groups[record["signature"]].append(record)

    duplicate_groups: List[Dict[str, Any]] = []

    for signature, records in signature_groups.items():
        if len(records) < 2:
            continue

        sorted_records = sorted(records, key=lambda item: item["asset_path"])
        total_slot_usage = sum(int(record["slot_usage_count"]) for record in sorted_records)

        duplicate_groups.append(
            {
                "signature": signature,
                "signature_info": _signature_to_dict(signature, include_extra_parameter_overrides),
                "asset_count": len(sorted_records),
                "total_slot_usage_count": total_slot_usage,
                "assets": sorted_records,
            }
        )

    duplicate_groups.sort(
        key=lambda group: (
            -int(group["asset_count"]),
            -int(group["total_slot_usage_count"]),
            str(group["signature_info"]["base_color_texture_name"]),
        )
    )

    return duplicate_groups


def _json_safe_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_path": record["asset_path"],
        "asset_name": record["asset_name"],
        "clean_asset_name": record["clean_asset_name"],
        "asset_class": record["asset_class"],
        "parent_material_path": record["parent_material_path"],
        "parent_material_name": record["parent_material_name"],
        "blend_mode_bucket": record["blend_mode_bucket"],
        "raw_blend_mode": record["raw_blend_mode"],
        "base_color_texture_name": record["base_color_texture_name"],
        "base_color_texture_path": record["base_color_texture_path"],
        "opacity_texture_name": record["opacity_texture_name"],
        "opacity_texture_path": record["opacity_texture_path"],
        "slot_usage_count": record["slot_usage_count"],
        "levels": sorted(record["levels"]),
        "level_package_paths": sorted(record["level_package_paths"]),
        "example_actors": list(record["example_actors"]),
        "example_meshes": list(record["example_meshes"]),
        "component_slots": list(record["component_slots"]),
    }


def _write_reports(report: Dict[str, Any]) -> Tuple[str, str]:
    output_dir = os.path.join(unreal.Paths.project_saved_dir(), "AssetConsolidator")
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "duplicate_material_analysis.json")
    csv_path = os.path.join(output_dir, "duplicate_material_analysis.csv")

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)

    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "group_index",
                "asset_path",
                "asset_name",
                "asset_class",
                "slot_usage_count",
                "levels",
                "level_package_paths",
                "parent_material_path",
                "blend_mode_bucket",
                "raw_blend_mode",
                "base_color_texture_name",
                "opacity_texture_name",
                "example_meshes",
                "example_actors",
            ]
        )

        for group_index, group in enumerate(report["duplicate_groups"], start=1):
            for asset_record in group["assets"]:
                writer.writerow(
                    [
                        group_index,
                        asset_record["asset_path"],
                        asset_record["asset_name"],
                        asset_record["asset_class"],
                        asset_record["slot_usage_count"],
                        ";".join(asset_record["levels"]),
                        ";".join(asset_record["level_package_paths"]),
                        asset_record["parent_material_path"],
                        asset_record["blend_mode_bucket"],
                        asset_record["raw_blend_mode"],
                        asset_record["base_color_texture_name"],
                        asset_record["opacity_texture_name"],
                        ";".join(asset_record["example_meshes"]),
                        ";".join(asset_record["example_actors"]),
                    ]
                )

    return json_path, csv_path


def _log_duplicate_groups(
    duplicate_groups: Sequence[Dict[str, Any]],
    max_log_groups: int,
    max_assets_per_group_log: int,
) -> None:
    if not duplicate_groups:
        _log("No duplicate material candidates found with the current signature.")
        return

    _log(f"Duplicate material candidate groups: {len(duplicate_groups)}")

    for group_index, group in enumerate(duplicate_groups[:max_log_groups], start=1):
        signature = group["signature_info"]
        _log(
            f"Group {group_index}: {group['asset_count']} material asset(s), "
            f"{group['total_slot_usage_count']} slot usage(s)"
        )
        _log(
            "  Signature: "
            f"Parent={signature['parent_material']} | "
            f"Blend={signature['blend_mode_bucket']} | "
            f"BaseColorTexture={signature['base_color_texture_name']} | "
            f"OpacityTexture={signature['opacity_texture_name']}"
        )

        for asset_record in group["assets"][:max_assets_per_group_log]:
            _log(
                f"    {asset_record['asset_path']} "
                f"(used by {asset_record['slot_usage_count']} material slot(s); "
                f"levels: {', '.join(asset_record['levels'])})"
            )
            if asset_record["example_meshes"]:
                _log(f"      Mesh examples: {', '.join(asset_record['example_meshes'])}")
            if asset_record["example_actors"]:
                _log(f"      Actor examples: {', '.join(asset_record['example_actors'])}")

        remaining = len(group["assets"]) - max_assets_per_group_log
        if remaining > 0:
            _log(f"    ...and {remaining} more material asset(s) in this group.")

    remaining_groups = len(duplicate_groups) - max_log_groups
    if remaining_groups > 0:
        _log(f"...and {remaining_groups} more duplicate group(s). See report files for full details.")


def analyze_duplicate_materials(
    write_report: bool = True,
    include_extra_parameter_overrides: bool = True,
    max_log_groups: int = 25,
    max_assets_per_group_log: int = 10,
) -> Dict[str, Any]:
    """
    Analyze loaded/open levels for duplicate-candidate material assets.

    Args:
        write_report: If True, writes JSON and CSV reports to Saved/AssetConsolidator.
        include_extra_parameter_overrides: If True, the duplicate signature also
            includes direct texture/scalar/vector parameter overrides. This is safer
            for later consolidation. Set False to compare only the requested parent,
            blend bucket, BaseColorTexture, and OpacityTexture keys.
        max_log_groups: Maximum duplicate groups to print to the Output Log.
        max_assets_per_group_log: Maximum assets per group to print to the Output Log.

    Returns:
        Dictionary report containing summary and duplicate_groups.
    """
    material_records, actor_level_infos, discovered_level_infos, material_slot_count = _collect_material_usage(
        include_extra_parameter_overrides
    )
    duplicate_groups = _build_duplicate_groups(material_records, include_extra_parameter_overrides)

    report_duplicate_groups = []
    for group in duplicate_groups:
        report_duplicate_groups.append(
            {
                "signature_info": group["signature_info"],
                "asset_count": group["asset_count"],
                "total_slot_usage_count": group["total_slot_usage_count"],
                "assets": [_json_safe_record(record) for record in group["assets"]],
            }
        )

    actor_level_names = [info["display_name"] for info in actor_level_infos]
    discovered_level_names = [info["display_name"] for info in discovered_level_infos]

    report = {
        "summary": {
            "actor_level_count": len(actor_level_names),
            "actor_levels_scanned": actor_level_names,
            "actor_level_details": actor_level_infos,
            "open_world_level_count": len(discovered_level_names),
            "open_world_levels_detected": discovered_level_names,
            "open_world_level_details": discovered_level_infos,
            "material_slot_usages_scanned": material_slot_count,
            "unique_material_asset_count": len(material_records),
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_candidate_asset_count": sum(group["asset_count"] for group in duplicate_groups),
            "include_extra_parameter_overrides": include_extra_parameter_overrides,
        },
        "duplicate_groups": report_duplicate_groups,
    }

    summary = report["summary"]
    _log("Analysis complete.")
    _log(
        "Open world levels discovered: "
        f"{summary['open_world_level_count']} - {_format_level_names(discovered_level_infos)}"
    )
    _log(
        "Actor level packages scanned: "
        f"{summary['actor_level_count']} - {_format_level_names(actor_level_infos)}"
    )
    _log(f"Material slot usages scanned: {summary['material_slot_usages_scanned']}")
    _log(f"Unique material assets found: {summary['unique_material_asset_count']}")
    _log(f"Extra parameter overrides included in signature: {summary['include_extra_parameter_overrides']}")
    _log(f"Duplicate candidate groups: {summary['duplicate_group_count']}")
    _log(f"Duplicate candidate material assets: {summary['duplicate_candidate_asset_count']}")

    if summary["open_world_level_count"] > 1 and summary["actor_level_count"] == 1:
        _warn(
            "Multiple open world levels were discovered, but scanned actors only reported one level package. "
            "This may mean the visible actors are all owned by the persistent level, or the current editor actor "
            "query is flattening level ownership."
        )

    _log_duplicate_groups(report_duplicate_groups, max_log_groups, max_assets_per_group_log)

    if write_report:
        json_path, csv_path = _write_reports(report)
        _log(f"Wrote JSON report: {json_path}")
        _log(f"Wrote CSV report:  {csv_path}")

    return report


if __name__ == "__main__":
    analyze_duplicate_materials()
