"""
move_environment_assets_to_folder.py

Unreal Editor Python helper for WBP_06_AssetConsolidator.

Organizes assets used by the currently loaded environment levels into a chosen
consolidation folder:
- <ConsolidateFolder>/Meshes
- <ConsolidateFolder>/Materials
- <ConsolidateFolder>/Textures

If consolidate_folder is not provided, the default is:
- <EnvironmentRoot>/Consolidated

Recommended default after mesh/material consolidation:
- active_component_materials_only=True
- include_static_mesh_default_slot_materials=False

This keeps material and texture organization focused on the materials actually active
on loaded components instead of also collecting old USD/default material slots that
may still exist on Static Mesh assets.
"""
from __future__ import annotations

import csv
import importlib
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import unreal
import analyze_duplicate_materials

importlib.reload(analyze_duplicate_materials)

LOG_PREFIX = "[AssetConsolidator OrganizeAssets]"

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
_get_parent_material = analyze_duplicate_materials._get_parent_material
_actor_level_info = analyze_duplicate_materials._actor_level_info


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _normalize_package_path(path: str) -> str:
    if not path:
        return ""
    path = str(path).replace("\\", "/")
    if "." in path:
        left, right = path.rsplit(".", 1)
        if right and "/" not in right:
            return left
    return path.rstrip("/")


def _package_path(asset: Any) -> str:
    if not asset:
        return ""
    try:
        package = asset.get_outermost()
        if package:
            name = package.get_name()
            if name:
                return _normalize_package_path(name)
    except Exception:
        pass
    return _normalize_package_path(_asset_path(asset))


def _asset_name_from_package(package_path: str) -> str:
    package_path = _normalize_package_path(package_path)
    return package_path.rsplit("/", 1)[-1] if package_path else "<None>"


def _folder_from_package(package_path: str) -> str:
    package_path = _normalize_package_path(package_path)
    if "/" not in package_path:
        return ""
    return package_path.rsplit("/", 1)[0]


def _is_under_path(path: str, root: str) -> bool:
    path = _normalize_package_path(path)
    root = _normalize_package_path(root)
    return bool(root) and (path == root or path.startswith(root + "/"))


def _get_editor_world() -> Optional[Any]:
    try:
        return unreal.EditorLevelLibrary.get_editor_world()
    except Exception:
        pass
    try:
        return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    except Exception:
        pass
    return None


def _world_package_path() -> str:
    world = _get_editor_world()
    if not world:
        return ""
    try:
        package = world.get_outermost()
        if package:
            return _normalize_package_path(package.get_name())
    except Exception:
        pass
    return ""


def _level_package_paths_from_actors() -> List[str]:
    level_paths: Dict[str, str] = {}
    for actor in _get_all_loaded_level_actors():
        if not actor:
            continue
        info = _actor_level_info(actor)
        package_path = _normalize_package_path(info.get("package_path", ""))
        display_name = info.get("display_name", _asset_name_from_package(package_path))
        if package_path.startswith("/Game/"):
            level_paths[package_path] = display_name
    return sorted(level_paths.keys())


def _auto_environment_root(
    explicit_environment_root: Optional[str] = None,
    explicit_top_level_path: Optional[str] = None,
) -> Tuple[str, str, List[str]]:
    level_package_paths = _level_package_paths_from_actors()

    if explicit_environment_root:
        return _normalize_package_path(explicit_environment_root), _normalize_package_path(explicit_top_level_path or ""), level_package_paths

    if explicit_top_level_path:
        top = _normalize_package_path(explicit_top_level_path)
        return _folder_from_package(top), top, level_package_paths

    world_path = _world_package_path()
    if world_path.startswith("/Game/") and "/sourceFiles/" not in world_path:
        return _folder_from_package(world_path), world_path, level_package_paths

    for level_path in level_package_paths:
        lower = level_path.lower()
        if "/sourcefiles/" in lower:
            continue
        if _asset_name_from_package(level_path).lower().startswith("lvl_"):
            return _folder_from_package(level_path), level_path, level_package_paths

    for level_path in level_package_paths:
        marker = "/sourceFiles/"
        if marker in level_path:
            return level_path.split(marker, 1)[0], "", level_package_paths

    if level_package_paths:
        folders = [_folder_from_package(path) for path in level_package_paths]
        common = os.path.commonprefix(folders).rstrip("/")
        if common.startswith("/Game/"):
            return common, "", level_package_paths

    return "", "", level_package_paths


def _resolve_consolidate_root(environment_root: str, consolidate_folder: Optional[str]) -> str:
    if consolidate_folder:
        root = _normalize_package_path(consolidate_folder)
    else:
        root = f"{_normalize_package_path(environment_root)}/Consolidated"

    if not root.startswith("/Game/"):
        raise RuntimeError("consolidate_folder must be a /Game/... Content Browser path.")

    return root.rstrip("/")


def _is_static_mesh(asset: Any) -> bool:
    try:
        return isinstance(asset, unreal.StaticMesh)
    except Exception:
        return "StaticMesh" in _class_name(asset)


def _is_material(asset: Any) -> bool:
    try:
        return isinstance(asset, unreal.MaterialInterface)
    except Exception:
        return "Material" in _class_name(asset)


def _is_texture(asset: Any) -> bool:
    try:
        return isinstance(asset, unreal.Texture)
    except Exception:
        return "Texture" in _class_name(asset)


def _add_asset_record(records: Dict[str, Dict[str, Any]], asset: Any, asset_type: str, reason: str, used_by: str = "") -> None:
    if not asset:
        return
    package_path = _package_path(asset)
    if not package_path.startswith("/Game/"):
        return
    if package_path not in records:
        records[package_path] = {
            "asset": asset,
            "asset_type": asset_type,
            "asset_name": _asset_name_from_package(package_path),
            "object_name": _object_name(asset),
            "object_path": _asset_path(asset),
            "package_path": package_path,
            "current_folder": _folder_from_package(package_path),
            "class_name": _class_name(asset),
            "reasons": set(),
            "used_by_examples": [],
        }
    records[package_path]["reasons"].add(reason)
    if used_by and used_by not in records[package_path]["used_by_examples"] and len(records[package_path]["used_by_examples"]) < 10:
        records[package_path]["used_by_examples"].append(used_by)


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


def _collect_static_meshes_and_materials(
    active_component_materials_only: bool = True,
    include_static_mesh_default_slot_materials: bool = False,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[str], int, int]:
    mesh_records: Dict[str, Dict[str, Any]] = {}
    material_records: Dict[str, Dict[str, Any]] = {}
    actors = _get_all_loaded_level_actors()
    level_paths = _level_package_paths_from_actors()
    component_count = 0
    material_slot_usage_count = 0
    collect_static_mesh_slots = bool(include_static_mesh_default_slot_materials and not active_component_materials_only)

    for actor in actors:
        if not actor:
            continue
        actor_name = _object_name(actor)
        level_info = _actor_level_info(actor)
        level_name = level_info.get("display_name", "<UnknownLevel>")

        for component in _get_static_mesh_components(actor):
            if not component:
                continue
            component_count += 1
            static_mesh = _component_static_mesh(component)
            if not static_mesh:
                continue

            static_mesh_name = _object_name(static_mesh)
            usage_label = f"{level_name}:{actor_name}:{static_mesh_name}"
            _add_asset_record(mesh_records, static_mesh, "StaticMesh", "StaticMeshComponent", usage_label)

            for material_index in range(_component_material_count(component)):
                material_slot_usage_count += 1
                material = _component_material(component, material_index)
                if not material:
                    continue
                if active_component_materials_only:
                    reason = "ActiveComponentMaterial"
                else:
                    override_material = _component_override_material(component, material_index)
                    reason = "ComponentMaterialOverride" if override_material else "ComponentEffectiveMaterial"
                _add_asset_record(material_records, material, "Material", reason, usage_label)

            if collect_static_mesh_slots:
                for static_material in _get_static_materials(static_mesh):
                    material = _static_material_interface(static_material)
                    if material:
                        _add_asset_record(material_records, material, "Material", "StaticMeshAssetSlot", static_mesh_name)

    return mesh_records, material_records, level_paths, component_count, material_slot_usage_count


def _direct_texture_parameter_values(material: Any) -> List[Any]:
    textures = []
    try:
        values = material.get_editor_property("texture_parameter_values")
        for value in values:
            try:
                texture = value.get_editor_property("parameter_value")
                if texture:
                    textures.append(texture)
            except Exception:
                pass
    except Exception:
        pass
    return textures


def _textures_used_by_material(material: Any) -> List[Any]:
    textures: Dict[str, Any] = {}
    try:
        used_textures = unreal.MaterialEditingLibrary.get_used_textures(material)
        if used_textures:
            for texture in used_textures:
                if texture:
                    textures[_package_path(texture)] = texture
    except Exception:
        pass

    current = material
    visited: Set[str] = set()
    while current:
        current_path = _package_path(current)
        if current_path in visited:
            break
        visited.add(current_path)
        for texture in _direct_texture_parameter_values(current):
            textures[_package_path(texture)] = texture
        current = _get_parent_material(current)

    return [texture for _, texture in sorted(textures.items())]


def _collect_textures(material_records: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    texture_records: Dict[str, Dict[str, Any]] = {}
    for material_record in material_records.values():
        material = material_record["asset"]
        material_name = material_record["asset_name"]
        for texture in _textures_used_by_material(material):
            if texture and _is_texture(texture):
                _add_asset_record(texture_records, texture, "Texture", "MaterialUsedTexture", material_name)
    return texture_records


def _make_directory(path: str) -> bool:
    try:
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            return True
    except Exception:
        pass
    try:
        return bool(unreal.EditorAssetLibrary.make_directory(path))
    except Exception:
        return False


def _asset_exists(package_path: str) -> bool:
    try:
        return bool(unreal.EditorAssetLibrary.does_asset_exist(package_path))
    except Exception:
        try:
            return bool(unreal.EditorAssetLibrary.load_asset(package_path))
        except Exception:
            return False


def _unique_destination_path(target_folder: str, asset_name: str, planned_destinations: Set[str]) -> Tuple[str, bool]:
    base = f"{target_folder}/{asset_name}"
    if base not in planned_destinations and not _asset_exists(base):
        return base, False
    for index in range(1, 10000):
        candidate = f"{base}_{index:03d}"
        if candidate not in planned_destinations and not _asset_exists(candidate):
            return candidate, True
    raise RuntimeError(f"Could not find unique destination path for {base}")


def _target_folder_for_type(asset_type: str, mesh_folder: str, material_folder: str, texture_folder: str) -> str:
    if asset_type == "StaticMesh":
        return mesh_folder
    if asset_type == "Material":
        return material_folder
    if asset_type == "Texture":
        return texture_folder
    return ""


def _plan_moves(
    asset_records_by_type: Dict[str, Dict[str, Dict[str, Any]]],
    environment_root: str,
    consolidate_root: str,
    mesh_folder: str,
    material_folder: str,
    texture_folder: str,
    move_only_assets_under_environment_root: bool,
) -> List[Dict[str, Any]]:
    operations: List[Dict[str, Any]] = []
    planned_destinations: Set[str] = set()

    for asset_type in ("StaticMesh", "Material", "Texture"):
        records = asset_records_by_type.get(asset_type, {})
        target_folder = _target_folder_for_type(asset_type, mesh_folder, material_folder, texture_folder)
        for package_path in sorted(records.keys()):
            record = records[package_path]
            status = "PLANNED"
            action = "WOULD_MOVE_ASSET"
            destination_path = ""
            reason = ""
            destination_was_suffixed = False

            if move_only_assets_under_environment_root and not _is_under_path(package_path, environment_root):
                status = "SKIPPED"
                action = "SKIP_EXTERNAL_ASSET"
                reason = "Asset is outside the environment root."
            elif _is_under_path(package_path, consolidate_root):
                status = "SKIPPED"
                action = "SKIP_ALREADY_IN_CONSOLIDATE_FOLDER"
                reason = "Asset is already under the consolidate folder."
            elif not target_folder:
                status = "SKIPPED"
                action = "SKIP_UNKNOWN_TYPE"
                reason = "No target folder for this asset type."
            else:
                destination_path, destination_was_suffixed = _unique_destination_path(target_folder, record["asset_name"], planned_destinations)
                planned_destinations.add(destination_path)

            operations.append({
                "asset_type": asset_type,
                "asset_name": record["asset_name"],
                "class_name": record["class_name"],
                "source_path": package_path,
                "source_object_path": record["object_path"],
                "source_folder": record["current_folder"],
                "destination_path": destination_path,
                "destination_folder": target_folder,
                "destination_was_suffixed": destination_was_suffixed,
                "action": action,
                "status": status,
                "reason": reason,
                "usage_reasons": sorted(record["reasons"]),
                "used_by_examples": list(record["used_by_examples"]),
            })
    return operations


def _execute_moves(operations: Sequence[Dict[str, Any]], save_moved_assets: bool) -> List[Dict[str, Any]]:
    executed: List[Dict[str, Any]] = []
    transaction = unreal.ScopedEditorTransaction("AssetConsolidator: Organize Environment Assets")
    transaction.__enter__()
    try:
        for op in operations:
            op = dict(op)
            if op["status"] == "SKIPPED":
                executed.append(op)
                continue
            try:
                ok = unreal.EditorAssetLibrary.rename_asset(op["source_path"], op["destination_path"])
                if not ok:
                    raise RuntimeError("EditorAssetLibrary.rename_asset returned False.")
                op["action"] = "MOVED_ASSET"
                op["status"] = "SUCCESS"
                if save_moved_assets:
                    try:
                        unreal.EditorAssetLibrary.save_asset(op["destination_path"], only_if_is_dirty=True)
                    except Exception as save_exc:
                        op["save_warning"] = str(save_exc)
            except Exception as exc:
                op["action"] = "MOVE_ASSET_FAILED"
                op["status"] = "ERROR"
                op["reason"] = str(exc)
            executed.append(op)
    finally:
        transaction.__exit__(None, None, None)
    return executed


def _report_dir() -> str:
    report_dir = os.path.join(unreal.Paths.project_saved_dir(), "AssetConsolidator")
    os.makedirs(report_dir, exist_ok=True)
    return report_dir


def _write_reports(report_name: str, summary: Dict[str, Any], operations: Sequence[Dict[str, Any]]) -> Tuple[str, str]:
    report_dir = _report_dir()
    json_path = os.path.join(report_dir, f"{report_name}.json")
    csv_path = os.path.join(report_dir, f"{report_name}.csv")

    payload = {"summary": summary, "operations": [dict(op) for op in operations]}
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)

    fieldnames = [
        "asset_type", "asset_name", "class_name", "status", "action",
        "source_path", "destination_path", "destination_was_suffixed",
        "reason", "usage_reasons", "used_by_examples",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for op in operations:
            row = {key: op.get(key, "") for key in fieldnames}
            row["usage_reasons"] = "; ".join(op.get("usage_reasons", []))
            row["used_by_examples"] = "; ".join(op.get("used_by_examples", []))
            writer.writerow(row)
    return json_path, csv_path


def _summarize_operations(operations: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "total_operations": len(operations),
        "move_candidate_count": 0,
        "skipped_count": 0,
        "success_count": 0,
        "error_count": 0,
        "suffixed_destination_count": 0,
        "by_type": {},
        "by_action": {},
        "by_status": {},
    }
    for op in operations:
        asset_type = op.get("asset_type", "Unknown")
        action = op.get("action", "Unknown")
        status = op.get("status", "Unknown")
        summary["by_type"].setdefault(asset_type, {"total": 0, "move_candidates": 0, "skipped": 0, "success": 0, "errors": 0})
        summary["by_type"][asset_type]["total"] += 1
        summary["by_action"][action] = summary["by_action"].get(action, 0) + 1
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        if action in ("WOULD_MOVE_ASSET", "MOVED_ASSET"):
            summary["move_candidate_count"] += 1
            summary["by_type"][asset_type]["move_candidates"] += 1
        if status == "SKIPPED":
            summary["skipped_count"] += 1
            summary["by_type"][asset_type]["skipped"] += 1
        if status == "SUCCESS":
            summary["success_count"] += 1
            summary["by_type"][asset_type]["success"] += 1
        if status == "ERROR":
            summary["error_count"] += 1
            summary["by_type"][asset_type]["errors"] += 1
        if op.get("destination_was_suffixed"):
            summary["suffixed_destination_count"] += 1
    return summary


def move_environment_assets_to_folder(
    dry_run: bool = True,
    write_report: bool = True,
    environment_root: Optional[str] = None,
    top_level_path: Optional[str] = None,
    consolidate_folder: Optional[str] = None,
    move_static_meshes: bool = True,
    move_materials: bool = True,
    move_textures: bool = True,
    move_only_assets_under_environment_root: bool = True,
    active_component_materials_only: bool = True,
    include_static_mesh_default_slot_materials: bool = False,
    save_moved_assets: bool = True,
    max_log_operations: int = 40,
) -> Dict[str, Any]:
    """Scan loaded levels and move used environment meshes/materials/textures into a chosen consolidate folder."""
    mode = "DRY RUN" if dry_run else "EXECUTE"
    _log(f"Starting environment asset organization. Mode: {mode}")
    if active_component_materials_only and include_static_mesh_default_slot_materials:
        _warn("active_component_materials_only=True, so include_static_mesh_default_slot_materials=True will be ignored.")

    env_root, detected_top_level_path, level_package_paths = _auto_environment_root(environment_root, top_level_path)
    if not env_root:
        raise RuntimeError("Could not determine environment root. Pass environment_root='/Game/...' explicitly.")

    consolidate_root = _resolve_consolidate_root(env_root, consolidate_folder)
    if not _is_under_path(consolidate_root, env_root):
        _warn("consolidate_folder is outside the environment root. This is allowed, but usually you want it inside the environment root.")

    mesh_folder = f"{consolidate_root}/Meshes"
    material_folder = f"{consolidate_root}/Materials"
    texture_folder = f"{consolidate_root}/Textures"
    used_static_mesh_slots = bool(include_static_mesh_default_slot_materials and not active_component_materials_only)

    _log(f"Top level package: {detected_top_level_path or '<Auto / not directly detected>'}")
    _log(f"Environment root: {env_root}")
    _log(f"Consolidate folder: {consolidate_root}")
    _log(f"Target mesh folder: {mesh_folder}")
    _log(f"Target material folder: {material_folder}")
    _log(f"Target texture folder: {texture_folder}")
    _log(f"active_component_materials_only: {active_component_materials_only}")
    _log(f"include_static_mesh_default_slot_materials: {used_static_mesh_slots}")
    _log(f"Actor level packages scanned: {len(level_package_paths)} - {', '.join(_asset_name_from_package(path) for path in level_package_paths) if level_package_paths else '<None>'}")

    mesh_records, material_records, _level_paths, component_count, material_slot_usage_count = _collect_static_meshes_and_materials(
        active_component_materials_only=active_component_materials_only,
        include_static_mesh_default_slot_materials=include_static_mesh_default_slot_materials,
    )
    texture_records = _collect_textures(material_records)

    asset_records_by_type = {
        "StaticMesh": mesh_records if move_static_meshes else {},
        "Material": material_records if move_materials else {},
        "Texture": texture_records if move_textures else {},
    }
    operations = _plan_moves(
        asset_records_by_type,
        env_root,
        consolidate_root,
        mesh_folder,
        material_folder,
        texture_folder,
        move_only_assets_under_environment_root,
    )

    if not dry_run:
        for folder in (mesh_folder, material_folder, texture_folder):
            if not _make_directory(folder):
                _warn(f"Could not create or confirm folder: {folder}")
        operations = _execute_moves(operations, save_moved_assets=save_moved_assets)

    op_summary = _summarize_operations(operations)
    summary = {
        "mode": mode,
        "dry_run": dry_run,
        "top_level_package_path": detected_top_level_path,
        "environment_root": env_root,
        "consolidate_folder": consolidate_root,
        "mesh_folder": mesh_folder,
        "material_folder": material_folder,
        "texture_folder": texture_folder,
        "actor_level_package_count": len(level_package_paths),
        "actor_level_package_paths": level_package_paths,
        "static_mesh_components_scanned": component_count,
        "material_slot_usages_scanned": material_slot_usage_count,
        "unique_static_mesh_assets_found": len(mesh_records),
        "unique_material_assets_found": len(material_records),
        "unique_texture_assets_found": len(texture_records),
        "move_static_meshes": move_static_meshes,
        "move_materials": move_materials,
        "move_textures": move_textures,
        "move_only_assets_under_environment_root": move_only_assets_under_environment_root,
        "active_component_materials_only": active_component_materials_only,
        "include_static_mesh_default_slot_materials_requested": include_static_mesh_default_slot_materials,
        "include_static_mesh_default_slot_materials_used": used_static_mesh_slots,
        **op_summary,
    }

    _log("Scan complete.")
    _log(f"Static mesh components scanned: {component_count}")
    _log(f"Material slot usages scanned: {material_slot_usage_count}")
    _log(f"Unique static mesh assets found: {len(mesh_records)}")
    _log(f"Unique material assets found: {len(material_records)}")
    _log(f"Unique texture assets found: {len(texture_records)}")
    _log(f"Move candidates: {op_summary['move_candidate_count']}")
    _log(f"Skipped assets: {op_summary['skipped_count']}")
    _log(f"Destination paths requiring numeric suffix: {op_summary['suffixed_destination_count']}")
    if not dry_run:
        _log(f"Successful moves: {op_summary['success_count']}")
        _log(f"Move errors: {op_summary['error_count']}")

    for asset_type in ("StaticMesh", "Material", "Texture"):
        type_info = op_summary["by_type"].get(asset_type, {})
        _log(
            f"{asset_type}: found={len(asset_records_by_type.get(asset_type, {}))}, "
            f"move_candidates={type_info.get('move_candidates', 0)}, skipped={type_info.get('skipped', 0)}, "
            f"success={type_info.get('success', 0)}, errors={type_info.get('errors', 0)}"
        )

    logged = 0
    for op in operations:
        if logged >= max_log_operations:
            remaining = len(operations) - logged
            if remaining > 0:
                _log(f"...and {remaining} more asset operation(s). See report files for full details.")
            break
        if op["action"] in ("WOULD_MOVE_ASSET", "MOVED_ASSET", "MOVE_ASSET_FAILED"):
            _log(f"{op['action']}: {op['asset_type']} {op['source_path']} -> {op['destination_path']}")
            logged += 1

    json_path = ""
    csv_path = ""
    if write_report:
        report_name = "move_environment_assets_to_folder_dry_run" if dry_run else "move_environment_assets_to_folder_executed"
        json_path, csv_path = _write_reports(report_name, summary, operations)
        _log(f"Wrote JSON report: {json_path}")
        _log(f"Wrote CSV report:  {csv_path}")

    _log(f"Organization {mode.lower()} complete. {op_summary['move_candidate_count']} asset(s) {'would be moved' if dry_run else 'processed for moving'}.")
    return {"summary": summary, "operations": operations, "json_report": json_path, "csv_report": csv_path}
