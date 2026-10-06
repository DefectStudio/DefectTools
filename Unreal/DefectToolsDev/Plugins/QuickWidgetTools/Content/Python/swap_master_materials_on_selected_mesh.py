"""
swap_master_materials_on_selected_mesh.py

Unreal Editor Python helper for WBP_05_MaterialSwapper.

Given:
- InputMaterial: the old material/material instance to match
- NewMasterMaterial: the new parent material/material instance to assign

The script scans the currently selected level actors, finds StaticMeshComponent
slot materials that either:
1. are exactly InputMaterial, or
2. have InputMaterial anywhere in their parent chain

Then it reparents those matching material instance assets to NewMasterMaterial.

This is intentionally asset-level reparenting, not per-component override swapping.
That means every mesh using the reparented MI asset will inherit the new parent.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Set

import unreal


LOG_PREFIX = "[MaterialSwapper Swap]"


def _log(message: str) -> None:
    unreal.log(f"{LOG_PREFIX} {message}")


def _warn(message: str) -> None:
    unreal.log_warning(f"{LOG_PREFIX} {message}")


def _error(message: str) -> None:
    unreal.log_error(f"{LOG_PREFIX} {message}")


def _load_asset(asset_or_path):
    """Accepts a UObject or asset path string and returns a loaded asset."""
    if not asset_or_path:
        return None

    if not isinstance(asset_or_path, str):
        return asset_or_path

    asset_path = asset_or_path.strip().strip('"').strip("'")
    if not asset_path:
        return None

    asset = unreal.load_asset(asset_path)
    if asset:
        return asset

    # Some Blueprint path strings come through as /Game/Folder/Asset instead of
    # /Game/Folder/Asset.Asset. Try the object path form as a fallback.
    if "." not in asset_path and "/" in asset_path:
        asset_name = asset_path.rsplit("/", 1)[-1]
        asset = unreal.load_asset(f"{asset_path}.{asset_name}")

    return asset


def _asset_path(asset) -> str:
    if not asset:
        return "<None>"
    try:
        return asset.get_path_name()
    except Exception:
        return str(asset)


def _same_asset(asset_a, asset_b) -> bool:
    if not asset_a or not asset_b:
        return False
    return _asset_path(asset_a) == _asset_path(asset_b)


def _get_parent_material(material):
    """Returns the parent material/interface for material instances, if any."""
    if not material:
        return None

    try:
        return material.get_editor_property("parent")
    except Exception:
        return None


def _material_matches(candidate_material, target_material, include_parent_chain: bool = True) -> bool:
    """
    True if candidate_material is target_material, or if target_material appears
    anywhere in candidate_material's parent chain when include_parent_chain is True.
    """
    if not candidate_material or not target_material:
        return False

    current = candidate_material
    visited: Set[str] = set()

    while current:
        current_path = _asset_path(current)
        if current_path in visited:
            break
        visited.add(current_path)

        if _same_asset(current, target_material):
            return True

        if not include_parent_chain:
            break

        current = _get_parent_material(current)

    return False


def _is_material_instance_constant(asset) -> bool:
    try:
        return isinstance(asset, unreal.MaterialInstanceConstant)
    except Exception:
        return False


def _get_editor_actor_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:
        return None


def _get_selected_level_actors() -> List[unreal.Actor]:
    actor_subsystem = _get_editor_actor_subsystem()
    if actor_subsystem:
        return list(actor_subsystem.get_selected_level_actors())

    # Fallback for older projects / editor API differences.
    return list(unreal.EditorLevelLibrary.get_selected_level_actors())


def _actor_static_mesh_components(actor: unreal.Actor) -> List[unreal.StaticMeshComponent]:
    try:
        return list(actor.get_components_by_class(unreal.StaticMeshComponent))
    except Exception:
        return []


def _collect_matching_slot_materials(
    selected_actors: List[unreal.Actor],
    input_material,
    new_master_material,
    include_parent_chain: bool,
) -> Dict[str, unreal.MaterialInstanceConstant]:
    """Returns unique MaterialInstanceConstant assets that should be reparented."""
    materials_to_reparent: Dict[str, unreal.MaterialInstanceConstant] = {}

    for actor in selected_actors:
        for component in _actor_static_mesh_components(actor):
            try:
                material_count = component.get_num_materials()
            except Exception:
                material_count = 0

            for material_index in range(material_count):
                try:
                    slot_material = component.get_material(material_index)
                except Exception:
                    slot_material = None

                if not _material_matches(slot_material, input_material, include_parent_chain=include_parent_chain):
                    continue

                if not _is_material_instance_constant(slot_material):
                    _warn(
                        "Matched slot material is not a MaterialInstanceConstant; skipping: "
                        f"{_asset_path(slot_material)}"
                    )
                    continue

                if _same_asset(slot_material, new_master_material):
                    _warn(f"Matched material is already the NewMasterMaterial; skipping: {_asset_path(slot_material)}")
                    continue

                # Prevent obvious parent loops: do not make a material instance child of
                # one of its own descendants.
                if _material_matches(new_master_material, slot_material, include_parent_chain=True):
                    _warn(
                        "Skipping because it would create a parent cycle: "
                        f"{_asset_path(slot_material)} -> {_asset_path(new_master_material)}"
                    )
                    continue

                materials_to_reparent[_asset_path(slot_material)] = slot_material

    return materials_to_reparent


def _set_material_instance_parent(material_instance, new_parent) -> bool:
    """Set parent with MaterialEditingLibrary, falling back to direct property set."""
    try:
        unreal.MaterialEditingLibrary.set_material_instance_parent(material_instance, new_parent)
        unreal.MaterialEditingLibrary.update_material_instance(material_instance)
        return True
    except Exception as exc:
        _warn(
            "MaterialEditingLibrary parent set failed; trying direct parent property set. "
            f"Material: {_asset_path(material_instance)} Error: {exc}"
        )

    try:
        material_instance.set_editor_property("parent", new_parent)
        unreal.MaterialEditingLibrary.update_material_instance(material_instance)
        return True
    except Exception as exc:
        _error(f"Failed to set parent on {_asset_path(material_instance)}: {exc}")
        return False


def _save_asset(asset) -> bool:
    try:
        return bool(unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False))
    except TypeError:
        # Some API versions do not expose only_if_is_dirty as a keyword.
        try:
            return bool(unreal.EditorAssetLibrary.save_loaded_asset(asset))
        except Exception:
            return False
    except Exception:
        return False


def swap_master_materials_on_selected_mesh(
    input_material,
    new_master_material,
    include_parent_chain: bool = True,
    save_assets: bool = True,
    dry_run: bool = False,
) -> List[unreal.MaterialInstanceConstant]:
    """
    Reparent matching material instance assets found on selected mesh actors.

    Args:
        input_material: Old material/material instance UObject or object path string.
        new_master_material: New parent MaterialInterface UObject or object path string.
        include_parent_chain: If True, slot material matches when input_material is
            anywhere in that slot material's parent chain.
        save_assets: If True, save changed material instance assets.
        dry_run: If True, report matches without changing assets.

    Returns:
        List of material instance assets that were changed, or would be changed in dry_run.
    """
    old_material = _load_asset(input_material)
    new_parent = _load_asset(new_master_material)

    if not old_material:
        _error(f"Could not load InputMaterial: {input_material}")
        return []

    if not new_parent:
        _error(f"Could not load NewMasterMaterial: {new_master_material}")
        return []

    selected_actors = _get_selected_level_actors()
    if not selected_actors:
        _warn("No selected level actors. Use SelectMeshes first, or manually select mesh actors before swapping.")
        return []

    _log(f"InputMaterial: {_asset_path(old_material)}")
    _log(f"NewMasterMaterial: {_asset_path(new_parent)}")
    _log(f"Selected actor count: {len(selected_actors)}")
    _log(f"Parent-chain matching: {include_parent_chain}")
    _log(f"Dry run: {dry_run}")

    materials_to_reparent = _collect_matching_slot_materials(
        selected_actors=selected_actors,
        input_material=old_material,
        new_master_material=new_parent,
        include_parent_chain=include_parent_chain,
    )

    if not materials_to_reparent:
        _warn("No matching material instance assets found on the selected mesh actors.")
        return []

    changed_materials: List[unreal.MaterialInstanceConstant] = []

    _log(f"Found {len(materials_to_reparent)} unique material instance asset(s) to reparent:")
    for material_path, material_instance in sorted(materials_to_reparent.items()):
        current_parent = _get_parent_material(material_instance)
        _log(f"  {material_path}")
        _log(f"    Current parent: {_asset_path(current_parent)}")
        _log(f"    New parent:     {_asset_path(new_parent)}")

        if dry_run:
            changed_materials.append(material_instance)
            continue

        if _set_material_instance_parent(material_instance, new_parent):
            changed_materials.append(material_instance)
            if save_assets:
                if _save_asset(material_instance):
                    _log(f"    Saved: {_asset_path(material_instance)}")
                else:
                    _warn(f"    Could not save asset: {_asset_path(material_instance)}")

    if dry_run:
        _log(f"Dry run complete. {len(changed_materials)} material instance asset(s) would be reparented.")
    else:
        _log(f"Swap complete. Reparented {len(changed_materials)} material instance asset(s).")

    return changed_materials


if __name__ == "__main__":
    if len(sys.argv) < 3:
        _error("Usage: swap_master_materials_on_selected_mesh.py <InputMaterialPath> <NewMasterMaterialPath>")
    else:
        swap_master_materials_on_selected_mesh(sys.argv[1], sys.argv[2])
