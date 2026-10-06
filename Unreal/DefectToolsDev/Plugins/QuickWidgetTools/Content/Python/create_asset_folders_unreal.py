"""
Create Unreal project folders for a pipeline asset.

Blueprint usage:
    import create_asset_folders_unreal
    import importlib
    importlib.reload(create_asset_folders_unreal)

    asset_folder_path = create_asset_folders_unreal.run(asset_name)

What this does:
    - Finds the Unreal show root by locating the root _showholder Blueprint asset.
    - Finds the Assets folder directly under that show root.
    - Creates an asset folder named after asset_name.
    - Creates _hero and sourceFiles subfolders inside the asset folder.
    - Creates a Blueprint asset named "_folderholder" in the asset folder and each subfolder.
    - The Blueprint parent class is Object.
    - Safe to re-run.

Example:
    asset_name: prp_ExampleProp

Creates:
    /Game/_s3bishop/Assets/prp_ExampleProp
    /Game/_s3bishop/Assets/prp_ExampleProp/_folderholder
    /Game/_s3bishop/Assets/prp_ExampleProp/_hero
    /Game/_s3bishop/Assets/prp_ExampleProp/_hero/_folderholder
    /Game/_s3bishop/Assets/prp_ExampleProp/sourceFiles
    /Game/_s3bishop/Assets/prp_ExampleProp/sourceFiles/_folderholder

Returns:
    str: Unreal asset folder path on success, or "" on failure.
"""

import re
import traceback
import unreal


LOG_PREFIX = "[CreateAssetFoldersUnreal]"
ASSETS_FOLDER_NAME = "Assets"
SHOW_HOLDER_ASSET_NAME = "_showholder"
PLACEHOLDER_ASSET_NAME = "_folderholder"
ASSET_SUBFOLDERS = ("_hero", "sourceFiles")


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _sanitize_asset_name(value):
    if value is None:
        return ""

    cleaned = str(value).strip()
    cleaned = cleaned.replace(" ", "_").replace("-", "_")
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")

    if cleaned and cleaned[0].isdigit():
        cleaned = f"asset_{cleaned}"

    return cleaned


def _get_package_path(asset_path):
    if not asset_path:
        return ""

    value = str(asset_path)
    folder_path, asset_reference_name = value.rsplit("/", 1)
    package_name = asset_reference_name.split(".", 1)[0]
    return f"{folder_path}/{package_name}"


def _get_asset_name_from_package_path(asset_path):
    package_path = _get_package_path(asset_path)
    return package_path.rsplit("/", 1)[-1]


def _get_folder_from_asset_path(asset_path):
    package_path = _get_package_path(asset_path)
    return package_path.rsplit("/", 1)[0]


def _get_placeholder_asset_path(folder_game_path):
    return f"{folder_game_path.rstrip('/')}/{PLACEHOLDER_ASSET_NAME}"


def _ensure_unreal_directory(game_path):
    if unreal.EditorAssetLibrary.does_directory_exist(game_path):
        return True

    if unreal.EditorAssetLibrary.make_directory(game_path):
        _log(f"Created folder: {game_path}")
        return True

    if unreal.EditorAssetLibrary.does_directory_exist(game_path):
        return True

    _log_error(f"Failed to create folder: {game_path}")
    return False


def _delete_asset_if_broken(asset_path):
    """
    If an asset exists at the path but is broken/invalid, try deleting it so it
    can be recreated.
    """
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return False

    loaded = unreal.EditorAssetLibrary.load_asset(asset_path)
    if loaded is not None:
        return False

    _log_warning(f"Found broken placeholder asset, deleting so it can be recreated: {asset_path}")
    deleted = unreal.EditorAssetLibrary.delete_asset(asset_path)
    if not deleted:
        raise RuntimeError(f"Failed to delete broken placeholder asset: {asset_path}")

    return True


def _ensure_placeholder_blueprint(folder_game_path):
    """
    Ensures a _folderholder Blueprint asset exists in the given folder.
    The Blueprint parent class is Object.

    Returns:
        ("created", asset_path) or ("exists", asset_path)
    """
    asset_path = _get_placeholder_asset_path(folder_game_path)

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        loaded_existing = unreal.EditorAssetLibrary.load_asset(asset_path)
        if loaded_existing is not None:
            return "exists", asset_path

        _delete_asset_if_broken(asset_path)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Object)
    factory.set_editor_property("edit_after_new", False)

    asset_obj = asset_tools.create_asset(
        asset_name=PLACEHOLDER_ASSET_NAME,
        package_path=folder_game_path,
        asset_class=unreal.Blueprint,
        factory=factory,
    )

    if not asset_obj:
        raise RuntimeError(f"Failed to create Blueprint placeholder: {asset_path}")

    saved = unreal.EditorAssetLibrary.save_asset(asset_path, only_if_is_dirty=False)
    if not saved:
        raise RuntimeError(f"Created placeholder Blueprint but failed to save: {asset_path}")

    loaded_after_save = unreal.EditorAssetLibrary.load_asset(asset_path)
    if loaded_after_save is None:
        raise RuntimeError(f"Placeholder Blueprint was created but could not be loaded after save: {asset_path}")

    return "created", asset_path


def _find_show_root_from_showholder():
    _log("Searching for root _showholder asset under /Game...")

    all_assets = unreal.EditorAssetLibrary.list_assets(
        "/Game",
        recursive=True,
        include_folder=False,
    )

    showholder_paths = []
    for asset_path in all_assets:
        package_path = _get_package_path(asset_path)
        asset_name = _get_asset_name_from_package_path(package_path)
        if asset_name != SHOW_HOLDER_ASSET_NAME:
            continue

        loaded_asset = unreal.EditorAssetLibrary.load_asset(package_path)
        if loaded_asset is None:
            _log_warning(f"Skipping unloadable _showholder candidate: {package_path}")
            continue

        showholder_paths.append(package_path)

    if not showholder_paths:
        _log_error("Could not find a _showholder asset under /Game.")
        return ""

    showholder_paths = sorted(set(showholder_paths))

    if len(showholder_paths) > 1:
        _log_error("Found more than one _showholder asset. Refusing to guess which show to use.")
        for path in showholder_paths:
            _log_error(f"  Candidate: {path}")
        return ""

    show_root = _get_folder_from_asset_path(showholder_paths[0])
    _log(f"Found show root: {show_root}")
    return show_root


def run(asset_name):
    try:
        _log(f"Raw asset_name input: {asset_name!r}")

        sanitized_asset_name = _sanitize_asset_name(asset_name)
        if not sanitized_asset_name:
            _log_error("asset_name was empty after sanitizing.")
            return ""

        show_root = _find_show_root_from_showholder()
        if not show_root:
            return ""

        assets_root = f"{show_root}/{ASSETS_FOLDER_NAME}"
        if not unreal.EditorAssetLibrary.does_directory_exist(assets_root):
            _log_error(f"Assets folder does not exist one folder below show root: {assets_root}")
            return ""

        asset_folder_path = f"{assets_root}/{sanitized_asset_name}"

        target_folder_paths = [asset_folder_path]
        for subfolder_name in ASSET_SUBFOLDERS:
            target_folder_paths.append(f"{asset_folder_path}/{subfolder_name}")

        for folder_path in target_folder_paths:
            if not _ensure_unreal_directory(folder_path):
                return ""

            asset_result, placeholder_asset_path = _ensure_placeholder_blueprint(folder_path)
            if asset_result == "created":
                _log(f"Created placeholder Blueprint: {placeholder_asset_path}")
            else:
                _log(f"Placeholder Blueprint already exists: {placeholder_asset_path}")

        try:
            unreal.EditorAssetLibrary.save_directory(asset_folder_path, only_if_is_dirty=False, recursive=True)
        except Exception as exc:
            _log_warning(f"save_directory warning on {asset_folder_path}: {exc}")

        _log(f"Created/validated Unreal asset folder structure: {asset_folder_path}")
        return asset_folder_path

    except Exception as exc:
        _log_error(str(exc))
        _log_error(traceback.format_exc())
        return ""
