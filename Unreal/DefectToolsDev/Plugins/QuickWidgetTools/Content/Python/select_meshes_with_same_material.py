"""
select_meshes_with_same_material.py

Unreal Editor Python helper for WBP_05_MaterialSwapper.

Given an input material/material instance, selects all level actors that have a
StaticMeshComponent using that material in any slot.

By default this also matches children in the material parent chain. Example:
- InputMaterial = UsdPreviewSurfaceTranslucentTwoSided
- Mesh slot material = MI_colony_simple_graphics_compMaterialSG2_TwoSided
- If that MI has UsdPreviewSurfaceTranslucentTwoSided anywhere in its parent chain,
  the actor will be selected.
"""

from __future__ import annotations

import sys
from typing import List, Optional, Set

import unreal


LOG_PREFIX = "[MaterialSwapper Select]"


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


def _get_editor_actor_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    except Exception:
        return None


def _get_all_level_actors() -> List[unreal.Actor]:
    actor_subsystem = _get_editor_actor_subsystem()
    if actor_subsystem:
        return list(actor_subsystem.get_all_level_actors())

    # Fallback for older projects / editor API differences.
    return list(unreal.EditorLevelLibrary.get_all_level_actors())


def _set_selected_level_actors(actors: List[unreal.Actor]) -> None:
    actor_subsystem = _get_editor_actor_subsystem()
    if actor_subsystem:
        actor_subsystem.set_selected_level_actors(actors)
        return

    # Fallback for older projects / editor API differences.
    unreal.EditorLevelLibrary.set_selected_level_actors(actors)


def _actor_static_mesh_components(actor: unreal.Actor) -> List[unreal.StaticMeshComponent]:
    try:
        return list(actor.get_components_by_class(unreal.StaticMeshComponent))
    except Exception:
        return []


def _component_uses_material(component: unreal.StaticMeshComponent, target_material, include_parent_chain: bool) -> bool:
    try:
        material_count = component.get_num_materials()
    except Exception:
        material_count = 0

    for material_index in range(material_count):
        try:
            slot_material = component.get_material(material_index)
        except Exception:
            slot_material = None

        if _material_matches(slot_material, target_material, include_parent_chain=include_parent_chain):
            return True

    return False


def select_meshes_with_same_material(input_material, include_parent_chain: bool = True) -> List[unreal.Actor]:
    """
    Select all level actors with StaticMeshComponents using input_material.

    Args:
        input_material: MaterialInterface UObject or object path string.
        include_parent_chain: If True, a mesh slot material also matches when
            input_material is in that slot material's parent chain.

    Returns:
        List of matched actors.
    """
    target_material = _load_asset(input_material)

    if not target_material:
        _error(f"Could not load InputMaterial: {input_material}")
        return []

    _log(f"Searching level actors for material: {_asset_path(target_material)}")
    _log(f"Parent-chain matching: {include_parent_chain}")

    matched_actors: List[unreal.Actor] = []

    for actor in _get_all_level_actors():
        for component in _actor_static_mesh_components(actor):
            if _component_uses_material(component, target_material, include_parent_chain=include_parent_chain):
                matched_actors.append(actor)
                break

    _set_selected_level_actors(matched_actors)

    _log(f"Selected {len(matched_actors)} actor(s).")
    for actor in matched_actors[:50]:
        _log(f"  {actor.get_actor_label()}")
    if len(matched_actors) > 50:
        _log(f"  ...and {len(matched_actors) - 50} more.")

    return matched_actors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _error("Usage: select_meshes_with_same_material.py <InputMaterialPath>")
    else:
        select_meshes_with_same_material(sys.argv[1])
