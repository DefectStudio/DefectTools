"""
swap_master_materials_on_selected_materials.py

Unreal Editor Python helper for WBP_05_MaterialSwapper.

Given:
- NewOpaqueMasterMaterial: the new parent material/material instance for opaque material instances
- NewMaskedMasterMaterial: the new parent material/material instance for non-opaque material instances

The script scans the materials/material instances selected in the Content Browser,
separates selected material instance assets by effective Blend Mode, then reparents:
1. Opaque material instances      -> NewOpaqueMasterMaterial
2. Any non-opaque material assets -> NewMaskedMasterMaterial

This is intentionally asset-level reparenting. It does not change individual mesh
component material slots.
"""

from __future__ import annotations

import sys
from typing import Dict, List, Optional, Sequence, Tuple

import unreal


LOG_PREFIX = "[MaterialSwapper BrowserSwap]"


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


def _class_name(asset) -> str:
    if not asset:
        return "<None>"
    try:
        return asset.get_class().get_name()
    except Exception:
        return type(asset).__name__


def _is_material_interface(asset) -> bool:
    if not asset:
        return False

    try:
        if isinstance(asset, unreal.MaterialInterface):
            return True
    except Exception:
        pass

    return _class_name(asset) in {
        "Material",
        "MaterialInstance",
        "MaterialInstanceConstant",
    }


def _is_material_instance_constant(asset) -> bool:
    try:
        return isinstance(asset, unreal.MaterialInstanceConstant)
    except Exception:
        return _class_name(asset) == "MaterialInstanceConstant"


def _get_parent_material(material):
    """Returns the parent material/interface for material instances, if any."""
    if not material:
        return None

    try:
        return material.get_editor_property("parent")
    except Exception:
        return None


def _material_has_parent(candidate_material, target_parent) -> bool:
    """True if target_parent is candidate_material or appears in its parent chain."""
    if not candidate_material or not target_parent:
        return False

    current = candidate_material
    visited = set()

    while current:
        current_path = _asset_path(current)
        if current_path in visited:
            break
        visited.add(current_path)

        if _same_asset(current, target_parent):
            return True

        current = _get_parent_material(current)

    return False


def _enum_to_string(value) -> str:
    if value is None:
        return "<None>"

    name = getattr(value, "name", None)
    if name:
        return str(name)

    return str(value)


def _get_direct_blend_mode(material):
    """
    Best-effort direct blend-mode lookup.

    MaterialInterface.GetBlendMode is the most useful path when available because it
    returns the effective blend mode. The property fallbacks are here for editor API
    differences between Unreal versions and asset classes.
    """
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


def _get_effective_blend_mode(material):
    """Returns the first discoverable/effective blend mode from the material/parent chain."""
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


def _is_opaque_blend_mode(blend_mode) -> bool:
    blend_mode_string = _enum_to_string(blend_mode).upper()
    return blend_mode_string.endswith("BLEND_OPAQUE") or blend_mode_string.endswith("OPAQUE")


def _get_selected_content_browser_assets() -> List[object]:
    try:
        return list(unreal.EditorUtilityLibrary.get_selected_assets())
    except Exception as exc:
        _error(f"Could not read selected Content Browser assets with EditorUtilityLibrary: {exc}")
        return []


def _dedupe_assets(assets: Sequence[object]) -> List[object]:
    unique_assets: Dict[str, object] = {}

    for asset in assets:
        if not asset:
            continue
        unique_assets[_asset_path(asset)] = asset

    return [unique_assets[path] for path in sorted(unique_assets.keys())]


def _collect_selected_material_instances() -> Tuple[List[object], List[object], List[object]]:
    """
    Returns: opaque_material_instances, non_opaque_material_instances, skipped_assets
    """
    selected_assets = _dedupe_assets(_get_selected_content_browser_assets())
    opaque_materials: List[object] = []
    non_opaque_materials: List[object] = []
    skipped_assets: List[object] = []

    for asset in selected_assets:
        if not _is_material_interface(asset):
            _warn(f"Skipping non-material asset: {_asset_path(asset)} ({_class_name(asset)})")
            skipped_assets.append(asset)
            continue

        if not _is_material_instance_constant(asset):
            _warn(
                "Skipping selected material because only MaterialInstanceConstant assets can be reparented: "
                f"{_asset_path(asset)} ({_class_name(asset)})"
            )
            skipped_assets.append(asset)
            continue

        blend_mode = _get_effective_blend_mode(asset)
        if blend_mode is None:
            _warn(f"Skipping material instance because its Blend Mode could not be resolved: {_asset_path(asset)}")
            skipped_assets.append(asset)
            continue

        if _is_opaque_blend_mode(blend_mode):
            opaque_materials.append(asset)
        else:
            non_opaque_materials.append(asset)

    return opaque_materials, non_opaque_materials, skipped_assets


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


def _reparent_material_group(
    material_instances: Sequence[object],
    new_parent,
    group_label: str,
    save_assets: bool,
    dry_run: bool,
) -> List[object]:
    changed_materials: List[object] = []

    _log(f"{group_label}: {len(material_instances)} material instance asset(s).")

    for material_instance in material_instances:
        current_parent = _get_parent_material(material_instance)

        if _same_asset(material_instance, new_parent):
            _warn(f"Skipping {group_label} material because it is the new parent itself: {_asset_path(material_instance)}")
            continue

        # Prevent obvious parent loops: do not make a material instance child of
        # one of its own descendants.
        if _material_has_parent(new_parent, material_instance):
            _warn(
                "Skipping because it would create a parent cycle: "
                f"{_asset_path(material_instance)} -> {_asset_path(new_parent)}"
            )
            continue

        _log(f"  {group_label}: {_asset_path(material_instance)}")
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

    return changed_materials


def swap_master_materials_on_selected_materials(
    new_opaque_master_material,
    new_masked_master_material,
    save_assets: bool = True,
    dry_run: bool = False,
) -> List[object]:
    """
    Reparent selected Content Browser material instance assets by Blend Mode.

    Args:
        new_opaque_master_material: New parent MaterialInterface UObject or object path string
            for selected material instances whose effective Blend Mode is Opaque.
        new_masked_master_material: New parent MaterialInterface UObject or object path string
            for selected material instances whose effective Blend Mode is anything other
            than Opaque. This includes Masked, Translucent, Additive, etc.
        save_assets: If True, save changed material instance assets.
        dry_run: If True, report matches without changing assets.

    Returns:
        List of material instance assets that were changed, or would be changed in dry_run.
    """
    new_opaque_parent = _load_asset(new_opaque_master_material)
    new_masked_parent = _load_asset(new_masked_master_material)

    if not new_opaque_parent:
        _error(f"Could not load NewOpaqueMasterMaterial: {new_opaque_master_material}")
        return []

    if not new_masked_parent:
        _error(f"Could not load NewMaskedMasterMaterial: {new_masked_master_material}")
        return []

    selected_assets = _get_selected_content_browser_assets()
    if not selected_assets:
        _warn("No selected Content Browser assets. Select material instance assets in the Content Browser first.")
        return []

    _log(f"NewOpaqueMasterMaterial: {_asset_path(new_opaque_parent)}")
    _log(f"NewMaskedMasterMaterial: {_asset_path(new_masked_parent)}")
    _log(f"Selected Content Browser asset count: {len(selected_assets)}")
    _log(f"Dry run: {dry_run}")

    opaque_materials, non_opaque_materials, skipped_assets = _collect_selected_material_instances()

    _log(f"OpaqueMaterials: {len(opaque_materials)}")
    _log(f"MaskedMaterials / NonOpaqueMaterials: {len(non_opaque_materials)}")
    _log(f"Skipped assets: {len(skipped_assets)}")

    if not opaque_materials and not non_opaque_materials:
        _warn("No selected MaterialInstanceConstant assets were eligible for reparenting.")
        return []

    changed_materials: List[object] = []
    changed_materials.extend(
        _reparent_material_group(
            material_instances=opaque_materials,
            new_parent=new_opaque_parent,
            group_label="OpaqueMaterials",
            save_assets=save_assets,
            dry_run=dry_run,
        )
    )
    changed_materials.extend(
        _reparent_material_group(
            material_instances=non_opaque_materials,
            new_parent=new_masked_parent,
            group_label="MaskedMaterials",
            save_assets=save_assets,
            dry_run=dry_run,
        )
    )

    if dry_run:
        _log(f"Dry run complete. {len(changed_materials)} material instance asset(s) would be reparented.")
    else:
        _log(f"Browser swap complete. Reparented {len(changed_materials)} material instance asset(s).")

    return changed_materials


if __name__ == "__main__":
    if len(sys.argv) < 3:
        _error(
            "Usage: swap_master_materials_on_selected_materials.py "
            "<NewOpaqueMasterMaterialPath> <NewMaskedMasterMaterialPath>"
        )
    else:
        swap_master_materials_on_selected_materials(sys.argv[1], sys.argv[2])
