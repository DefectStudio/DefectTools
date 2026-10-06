"""
analyze_duplicate_static_meshes.py

Unreal Editor Python helper for WBP_06_AssetConsolidator.

Scans all currently loaded actors in the open level and loaded/open sublevels,
collects StaticMeshComponent static mesh assets, and reports duplicate-candidate
static mesh assets using a conservative signature:

- cleaned static mesh base name
- LOD0 vertex count when available, otherwise triangle count when available
- material slot count
- cleaned material asset names assigned to the static mesh asset's slots

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


LOG_PREFIX = "[AssetConsolidator MeshAnalyze]"


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


def _clean_base_name(name_or_asset: Any) -> str:
    """
    Normalize imported USD/Maya-ish asset names enough to find obvious duplicates.

    Example:
        SM_colony__util__crate__lg__c__1Shape1_2346
        -> sm_colony_util_crate_lg_c_1shape1

    This intentionally does not remove Shape1, LOD labels, or meaningful middle
    tokens. It mostly removes Unreal/USD copy or placement number suffixes.
    """
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

    suffix_patterns = [
        r"(_copy\d*)$",
        r"(_duplicate\d*)$",
        r"(_inst\d*)$",
        r"(_\d+)$",
    ]

    changed = True
    while changed:
        changed = False
        for pattern in suffix_patterns:
            new_name = re.sub(pattern, "", name)
            if new_name != name:
                name = new_name
                changed = True

    name = re.sub(r"__+", "_", name)
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
            # Example: /Game/Maps/MyMap.MyMap:PersistentLevel
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


def _static_material_slot_name(static_material: Any) -> str:
    for prop_name in ("material_slot_name", "MaterialSlotName"):
        try:
            value = static_material.get_editor_property(prop_name)
            if value:
                return str(value)
        except Exception:
            pass

    return "<None>"


def _call_with_possible_lod(function: Any, static_mesh: Any) -> Optional[int]:
    for args in ((static_mesh, 0), (static_mesh,)):
        try:
            value = function(*args)
            if value is not None:
                return int(value)
        except Exception:
            pass
    return None


def _get_vertex_count(static_mesh: Any) -> Optional[int]:
    lib = getattr(unreal, "EditorStaticMeshLibrary", None)
    if lib:
        for function_name in ("get_number_verts", "get_num_vertices", "get_number_vertices"):
            function = getattr(lib, function_name, None)
            if function:
                value = _call_with_possible_lod(function, static_mesh)
                if value is not None:
                    return value

    for method_name in ("get_num_vertices", "get_number_verts", "get_number_vertices"):
        method = getattr(static_mesh, method_name, None)
        if method:
            value = _call_with_possible_lod(method, static_mesh)
            if value is not None:
                return value

    return None


def _get_triangle_count(static_mesh: Any) -> Optional[int]:
    lib = getattr(unreal, "EditorStaticMeshLibrary", None)
    if lib:
        for function_name in ("get_number_triangles", "get_num_triangles", "get_triangle_count"):
            function = getattr(lib, function_name, None)
            if function:
                value = _call_with_possible_lod(function, static_mesh)
                if value is not None:
                    return value

    for method_name in ("get_num_triangles", "get_number_triangles", "get_triangle_count"):
        method = getattr(static_mesh, method_name, None)
        if method:
            value = _call_with_possible_lod(method, static_mesh)
            if value is not None:
                return value

    return None


def _geometry_measure(static_mesh: Any) -> Tuple[str, Any]:
    vertex_count = _get_vertex_count(static_mesh)
    if vertex_count is not None:
        return "VERTS_LOD0", vertex_count

    triangle_count = _get_triangle_count(static_mesh)
    if triangle_count is not None:
        return "TRIS_LOD0", triangle_count

    # Safer than grouping unknown geometry together.
    return "UNKNOWN_GEOMETRY_COUNT", _asset_path(static_mesh)


def _mesh_material_names(static_mesh: Any) -> Tuple[str, ...]:
    material_names: List[str] = []

    for static_material in _get_static_materials(static_mesh):
        material = _static_material_interface(static_material)
        if material:
            material_names.append(_clean_base_name(material))
        else:
            slot_name = _clean_base_name(_static_material_slot_name(static_material))
            material_names.append(f"<empty:{slot_name}>")

    return tuple(material_names)


def _mesh_signature(static_mesh: Any) -> Tuple[Any, ...]:
    material_names = _mesh_material_names(static_mesh)
    geometry_label, geometry_value = _geometry_measure(static_mesh)

    return (
        _clean_base_name(static_mesh),
        geometry_label,
        geometry_value,
        len(material_names),
        material_names,
    )


def _signature_to_dict(signature: Tuple[Any, ...]) -> Dict[str, Any]:
    return {
        "clean_base_name": signature[0],
        "geometry_count_type": signature[1],
        "geometry_count_value": signature[2],
        "material_slot_count": signature[3],
        "material_names": list(signature[4]),
    }


def _collect_static_mesh_usage() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]], int]:
    actors = _get_all_loaded_level_actors()
    discovered_level_infos = _discover_open_world_levels()

    mesh_records: Dict[str, Dict[str, Any]] = {}
    actor_level_infos_by_package: Dict[str, Dict[str, str]] = {}
    component_count = 0

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
            if not static_mesh:
                continue

            component_count += 1
            mesh_path = _asset_path(static_mesh)

            if mesh_path not in mesh_records:
                mesh_records[mesh_path] = {
                    "asset": static_mesh,
                    "asset_path": mesh_path,
                    "asset_name": _object_name(static_mesh),
                    "clean_base_name": _clean_base_name(static_mesh),
                    "signature": _mesh_signature(static_mesh),
                    "component_count": 0,
                    "levels": set(),
                    "level_package_paths": set(),
                    "example_actors": [],
                    "component_paths": [],
                }

            record = mesh_records[mesh_path]
            record["component_count"] += 1
            record["levels"].add(level_name)
            record["level_package_paths"].add(level_info.get("package_path", "<UnknownLevel>"))

            if len(record["example_actors"]) < 10:
                record["example_actors"].append(actor_name)

            if len(record["component_paths"]) < 10:
                record["component_paths"].append(_asset_path(component))

    actor_level_infos = sorted(
        actor_level_infos_by_package.values(),
        key=lambda item: item.get("display_name", ""),
    )

    return mesh_records, actor_level_infos, discovered_level_infos, component_count


def _build_duplicate_groups(mesh_records: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    signature_groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)

    for record in mesh_records.values():
        signature_groups[record["signature"]].append(record)

    duplicate_groups: List[Dict[str, Any]] = []

    for signature, records in signature_groups.items():
        if len(records) < 2:
            continue

        sorted_records = sorted(records, key=lambda item: item["asset_path"])
        total_component_count = sum(int(record["component_count"]) for record in sorted_records)

        duplicate_groups.append(
            {
                "signature": signature,
                "signature_info": _signature_to_dict(signature),
                "asset_count": len(sorted_records),
                "total_component_count": total_component_count,
                "assets": sorted_records,
            }
        )

    duplicate_groups.sort(
        key=lambda group: (
            -int(group["asset_count"]),
            -int(group["total_component_count"]),
            str(group["signature_info"]["clean_base_name"]),
        )
    )

    return duplicate_groups


def _json_safe_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_path": record["asset_path"],
        "asset_name": record["asset_name"],
        "clean_base_name": record["clean_base_name"],
        "component_count": record["component_count"],
        "levels": sorted(record["levels"]),
        "level_package_paths": sorted(record["level_package_paths"]),
        "example_actors": list(record["example_actors"]),
        "component_paths": list(record["component_paths"]),
    }


def _write_reports(report: Dict[str, Any]) -> Tuple[str, str]:
    output_dir = os.path.join(unreal.Paths.project_saved_dir(), "AssetConsolidator")
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "duplicate_static_mesh_analysis.json")
    csv_path = os.path.join(output_dir, "duplicate_static_mesh_analysis.csv")

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)

    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "group_index",
                "asset_path",
                "asset_name",
                "component_count",
                "levels",
                "level_package_paths",
                "clean_base_name",
                "geometry_count_type",
                "geometry_count_value",
                "material_slot_count",
                "material_names",
                "example_actors",
            ]
        )

        for group_index, group in enumerate(report["duplicate_groups"], start=1):
            signature = group["signature_info"]
            for asset_record in group["assets"]:
                writer.writerow(
                    [
                        group_index,
                        asset_record["asset_path"],
                        asset_record["asset_name"],
                        asset_record["component_count"],
                        ";".join(asset_record["levels"]),
                        ";".join(asset_record["level_package_paths"]),
                        signature["clean_base_name"],
                        signature["geometry_count_type"],
                        signature["geometry_count_value"],
                        signature["material_slot_count"],
                        ";".join(signature["material_names"]),
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
        _log("No duplicate static mesh candidates found with the current signature.")
        return

    _log(f"Duplicate static mesh candidate groups: {len(duplicate_groups)}")

    for group_index, group in enumerate(duplicate_groups[:max_log_groups], start=1):
        signature = group["signature_info"]
        _log(
            f"Group {group_index}: {group['asset_count']} mesh asset(s), "
            f"{group['total_component_count']} placed component(s)"
        )
        _log(
            "  Signature: "
            f"BaseName={signature['clean_base_name']} | "
            f"{signature['geometry_count_type']}={signature['geometry_count_value']} | "
            f"MaterialSlots={signature['material_slot_count']} | "
            f"Materials={signature['material_names']}"
        )

        for asset_record in group["assets"][:max_assets_per_group_log]:
            _log(
                f"    {asset_record['asset_path']} "
                f"(used by {asset_record['component_count']} component(s); "
                f"levels: {', '.join(asset_record['levels'])})"
            )
            if asset_record["example_actors"]:
                _log(f"      Examples: {', '.join(asset_record['example_actors'])}")

        remaining = len(group["assets"]) - max_assets_per_group_log
        if remaining > 0:
            _log(f"    ...and {remaining} more asset(s) in this group.")

    remaining_groups = len(duplicate_groups) - max_log_groups
    if remaining_groups > 0:
        _log(f"...and {remaining_groups} more duplicate group(s). See report files for full details.")


def analyze_duplicate_static_meshes(
    write_report: bool = True,
    max_log_groups: int = 25,
    max_assets_per_group_log: int = 10,
) -> Dict[str, Any]:
    """
    Analyze loaded/open levels for duplicate-candidate Static Mesh assets.

    Args:
        write_report: If True, writes JSON and CSV reports to Saved/AssetConsolidator.
        max_log_groups: Maximum duplicate groups to print to the Output Log.
        max_assets_per_group_log: Maximum assets per group to print to the Output Log.

    Returns:
        Dictionary report containing summary and duplicate_groups.
    """
    mesh_records, actor_level_infos, discovered_level_infos, component_count = _collect_static_mesh_usage()
    duplicate_groups = _build_duplicate_groups(mesh_records)

    report_duplicate_groups = []
    for group in duplicate_groups:
        report_duplicate_groups.append(
            {
                "signature_info": group["signature_info"],
                "asset_count": group["asset_count"],
                "total_component_count": group["total_component_count"],
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
            "static_mesh_component_count": component_count,
            "unique_static_mesh_asset_count": len(mesh_records),
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_candidate_asset_count": sum(group["asset_count"] for group in duplicate_groups),
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
    _log(f"Static mesh components scanned: {summary['static_mesh_component_count']}")
    _log(f"Unique static mesh assets found: {summary['unique_static_mesh_asset_count']}")
    _log(f"Duplicate candidate groups: {summary['duplicate_group_count']}")
    _log(f"Duplicate candidate mesh assets: {summary['duplicate_candidate_asset_count']}")

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
    analyze_duplicate_static_meshes()
