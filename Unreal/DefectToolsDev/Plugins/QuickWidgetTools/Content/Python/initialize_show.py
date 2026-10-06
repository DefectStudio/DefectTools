# -*- coding: utf-8 -*-
"""
initialize_show.py

Designed to be called from an Editor Utility Widget via:
    import initialize_show
    import importlib
    importlib.reload(initialize_show)
    initialize_show.run(show_name)

What it does:
- Accepts a show name string from Blueprint
- Writes show_name to Saved/Config/WindowsEditor/QuickWidgetToolsSettings.ini
- If the show already exists, stops there and does not touch Unreal folders/assets or file-server folders
- If the show does not exist, creates the starter Unreal show folder tree and placeholder Blueprints
- If the show does not exist and ShowFileServerPath is saved, creates missing starter file-server folders
- Never recursively saves the whole show directory
- Safe to re-run
- Logs all actions
"""

import json
import os
import re
import traceback

import unreal


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

DEFAULT_SHOW_NAME = "showname"
PLACEHOLDER_ASSET_NAME = "_folderholder"
ROOT_PLACEHOLDER_ASSET_NAME = "_showholder"

SETTINGS_FILE_NAME = "QuickWidgetToolsSettings.ini"
SETTINGS_SECTION = "/Script/QuickWidgetTools.RenderToolSettings"
SHOW_NAME_SETTINGS_KEY = "show_name"
SHOW_FILE_SERVER_PATH_KEY = "ShowFileServerPath"

SHOW_MANIFEST_FILE_NAME = "_show_manifest.json"

FOLDER_TREE = {
    "Assets": [
        "chr_ExampleCharacter",
        "lvl_ExampleLevel",
        "prp_ExampleProp",
        "fol_ExampleFoliage",
        "vhl_ExampleVehicle",
        "mat_ExampleMaterial",
        "msc_ExampleMisc",
        "fx_ExampleFX",
    ],
    "Sequences": [],
    "RenderSettings": [
        "OCIO",
    ],
    "Audio": [],
}

# File-server folders intentionally stay simple at show init time.
# Per-shot folders are handled by create_shot_file_server_folders.py.
FILE_SERVER_TOP_LEVEL_FOLDERS = (
    "assets",
    "sequences",
    "render_settings",
    "audio",
)


# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

def log(message):
    unreal.log(f"[InitializeShow] {message}")


def log_warning(message):
    unreal.log_warning(f"[InitializeShow] {message}")


def log_error(message):
    unreal.log_error(f"[InitializeShow] {message}")


# -----------------------------------------------------------------------------
# Name utilities
# -----------------------------------------------------------------------------

def to_lower_safe_name(raw_text):
    parts = re.findall(r"[A-Za-z0-9]+", raw_text or "")
    return "".join(parts).lower()


def sanitize_show_name(user_text):
    """
    Builds the default new-show folder name.

    Existing show folders are resolved separately with exact casing, so entering
    S3Bishop can correctly match /Game/_S3Bishop instead of forcing /Game/_s3bishop.
    """
    cleaned = to_lower_safe_name((user_text or "").strip())
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned)

    if not cleaned:
        cleaned = DEFAULT_SHOW_NAME

    if cleaned[0].isdigit():
        cleaned = "show" + cleaned

    return "_" + cleaned


def show_match_key(value):
    text = str(value or "").strip()
    if text.startswith("_"):
        text = text[1:]
    return to_lower_safe_name(text)


# -----------------------------------------------------------------------------
# Unreal path helpers
# -----------------------------------------------------------------------------

def join_game_path(parent, child):
    return f"{parent.rstrip('/')}/{child.strip('/')}"


def build_all_game_paths(show_folder_name):
    """
    Returns every folder path we want, including the root show folder.
    """
    root = f"/Game/{show_folder_name}"
    paths = [root]

    for top_level, children in FOLDER_TREE.items():
        top_path = join_game_path(root, top_level)
        paths.append(top_path)

        for child in children:
            child_path = join_game_path(top_path, child)
            paths.append(child_path)

    return paths


def get_placeholder_asset_name(folder_game_path, root_game_path):
    if folder_game_path.rstrip("/") == root_game_path.rstrip("/"):
        return ROOT_PLACEHOLDER_ASSET_NAME
    return PLACEHOLDER_ASSET_NAME


def get_placeholder_asset_path(folder_game_path, root_game_path):
    placeholder_asset_name = get_placeholder_asset_name(folder_game_path, root_game_path)
    return f"{folder_game_path.rstrip('/')}/{placeholder_asset_name}"


def find_existing_show_root_game_path(requested_show_name, fallback_sanitized_show_name):
    """
    Returns:
        (root_game_path, exists)

    This searches top-level /Game folders for a case-insensitive show-name match
    and uses the exact existing folder path when found.
    """
    target_key = show_match_key(requested_show_name)
    fallback_root = f"/Game/{fallback_sanitized_show_name}"

    try:
        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        sub_paths = asset_registry.get_sub_paths("/Game", recurse=False)
    except Exception as exc:
        log_warning(f"Could not query /Game sub paths from asset registry: {exc}")
        sub_paths = []

    for folder_path in sorted(sub_paths):
        folder_name = folder_path.split("/")[-1]
        if not folder_name.startswith("_"):
            continue
        if show_match_key(folder_name) != target_key:
            continue

        showholder_asset_path = f"{folder_path.rstrip('/')}/{ROOT_PLACEHOLDER_ASSET_NAME}"
        if unreal.EditorAssetLibrary.does_asset_exist(showholder_asset_path):
            log(f"Found existing show folder by _showholder: {folder_path}")
            return folder_path, True

        if unreal.EditorAssetLibrary.does_directory_exist(folder_path):
            log(f"Found existing show folder by directory match: {folder_path}")
            return folder_path, True

    if unreal.EditorAssetLibrary.does_directory_exist(fallback_root):
        log(f"Found existing show folder by fallback path: {fallback_root}")
        return fallback_root, True

    return fallback_root, False


# -----------------------------------------------------------------------------
# Settings helpers
# -----------------------------------------------------------------------------

def normalize_file_path(path_value):
    value = str(path_value or "").strip()
    if not value:
        return ""

    value = value.replace("\\", "/")
    while "//" in value:
        value = value.replace("//", "/")

    return value.rstrip("/")


def find_config_dir(project_dir):
    candidates = [
        os.path.join(project_dir, "Saved", "Config", "WindowsEditor"),
        os.path.join(project_dir, "Saved", "Config", "Windows"),
        os.path.join(project_dir, "Saved", "Config"),
    ]

    for folder in candidates:
        log(f"Checking config folder candidate: {folder}")
        if os.path.isdir(folder):
            log(f"Using existing config folder: {folder}")
            return folder

    fallback = os.path.join(project_dir, "Saved", "Config", "WindowsEditor")
    log_warning(f"No candidate config folder existed. Falling back to: {fallback}")
    return fallback


def get_settings_file_path():
    project_dir = unreal.Paths.project_dir()
    log(f"Project dir: {project_dir}")

    config_dir = find_config_dir(project_dir)
    settings_path = os.path.join(config_dir, SETTINGS_FILE_NAME)
    settings_path = os.path.normpath(settings_path)

    log(f"Resolved settings file path: {settings_path}")
    return settings_path


def read_text_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text_file(path, text):
    settings_dir = os.path.dirname(path)
    if settings_dir:
        os.makedirs(settings_dir, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def find_section_bounds(lines, section_name):
    section_header = f"[{section_name}]"
    section_start = -1
    section_end = len(lines)

    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_start = i
            break

    if section_start == -1:
        return -1, -1

    for i in range(section_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section_end = i
            break

    return section_start, section_end


def get_section_value(text, section_name, key):
    lines = text.splitlines()
    section_start, section_end = find_section_bounds(lines, section_name)
    if section_start == -1:
        return ""

    prefix = f"{key}="
    for i in range(section_start + 1, section_end):
        stripped = lines[i].strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()

    return ""


def upsert_section_key(existing_text, section_name, key, value):
    lines = existing_text.splitlines()
    section_header = f"[{section_name}]"
    new_key_line = f"{key}={value}"

    section_start, section_end = find_section_bounds(lines, section_name)

    if section_start == -1:
        log(f"Section not found. Appending new section: {section_header}")
        if existing_text and not existing_text.endswith("\n"):
            existing_text += "\n"
        if existing_text and not existing_text.endswith("\n\n"):
            existing_text += "\n"
        existing_text += f"{section_header}\n{new_key_line}\n"
        return existing_text

    prefix = f"{key}="
    for i in range(section_start + 1, section_end):
        stripped = lines[i].strip()
        if stripped.startswith(prefix):
            if lines[i] == new_key_line:
                log(f"Settings key already correct: {key}={value}")
            else:
                log(f"Updating {key} on line {i + 1}.")
                lines[i] = new_key_line
            return "\n".join(lines) + "\n"

    log(f"Adding {key} inside existing section before line {section_end + 1}.")
    lines.insert(section_end, new_key_line)
    return "\n".join(lines) + "\n"


def write_show_name_setting(requested_show_name):
    """
    Writes:
        [/Script/QuickWidgetTools.RenderToolSettings]
        show_name=<requested_show_name>
    """
    settings_path = get_settings_file_path()
    show_name_value = str(requested_show_name or DEFAULT_SHOW_NAME).strip() or DEFAULT_SHOW_NAME

    before_text = read_text_file(settings_path)
    updated_text = upsert_section_key(
        existing_text=before_text,
        section_name=SETTINGS_SECTION,
        key=SHOW_NAME_SETTINGS_KEY,
        value=show_name_value,
    )

    if updated_text != before_text:
        write_text_file(settings_path, updated_text)
        log(f"Wrote {SHOW_NAME_SETTINGS_KEY}='{show_name_value}' to settings file: {settings_path}")
    else:
        log(f"Settings file already has {SHOW_NAME_SETTINGS_KEY}='{show_name_value}'")

    verified_text = read_text_file(settings_path)
    verified_value = get_section_value(verified_text, SETTINGS_SECTION, SHOW_NAME_SETTINGS_KEY)
    if verified_value != show_name_value:
        raise RuntimeError(
            f"Post-write verification failed. Expected {SHOW_NAME_SETTINGS_KEY}='{show_name_value}' "
            f"but found '{verified_value}'"
        )

    return settings_path, show_name_value


def get_saved_show_file_server_path():
    settings_path = get_settings_file_path()
    if not os.path.exists(settings_path):
        log_warning(f"Settings file does not exist yet. Skipping file-server init: {settings_path}")
        return ""

    text = read_text_file(settings_path)
    saved_path = get_section_value(text, SETTINGS_SECTION, SHOW_FILE_SERVER_PATH_KEY)
    saved_path = normalize_file_path(saved_path)

    if not saved_path:
        log_warning(
            f"No {SHOW_FILE_SERVER_PATH_KEY} found in [{SETTINGS_SECTION}]. "
            "Skipping file-server init."
        )
        return ""

    log(f"Loaded {SHOW_FILE_SERVER_PATH_KEY}: {saved_path}")
    return saved_path


# -----------------------------------------------------------------------------
# Unreal folder helpers
# -----------------------------------------------------------------------------

def ensure_unreal_directory(game_path):
    """
    Creates the Unreal directory if missing.
    Returns:
        "created" or "exists"
    Raises on unexpected errors.
    """
    if unreal.EditorAssetLibrary.does_directory_exist(game_path):
        return "exists"

    ok = unreal.EditorAssetLibrary.make_directory(game_path)
    if not ok:
        if unreal.EditorAssetLibrary.does_directory_exist(game_path):
            return "exists"
        raise RuntimeError(f"Failed to create directory: {game_path}")

    return "created"


# -----------------------------------------------------------------------------
# Blueprint placeholder helpers
# -----------------------------------------------------------------------------

def ensure_placeholder_blueprint(folder_game_path, root_game_path):
    """
    Ensures a placeholder Blueprint asset exists in the given folder.
    The Blueprint parent class is Object.

    If an asset already exists at the target path, it is left alone and is not
    deleted, recreated, or overwritten.

    Returns:
        ("created", asset_path) or ("exists", asset_path)
    """
    placeholder_asset_name = get_placeholder_asset_name(folder_game_path, root_game_path)
    asset_path = get_placeholder_asset_path(folder_game_path, root_game_path)

    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        return "exists", asset_path

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.Object)
    factory.set_editor_property("edit_after_new", False)

    asset_obj = asset_tools.create_asset(
        asset_name=placeholder_asset_name,
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


# -----------------------------------------------------------------------------
# File-server helpers
# -----------------------------------------------------------------------------

def build_file_server_folder_paths(show_root_path):
    root = normalize_file_path(show_root_path)
    if not root:
        return []

    paths = [root]
    for folder_name in FILE_SERVER_TOP_LEVEL_FOLDERS:
        paths.append(os.path.join(root, folder_name))

    return [os.path.normpath(path) for path in paths]


def ensure_file_server_directory(folder_path):
    normalized = os.path.normpath(str(folder_path or "").strip())
    if not normalized:
        raise RuntimeError("File-server folder path was empty.")

    if os.path.isdir(normalized):
        return "exists"

    os.makedirs(normalized, exist_ok=True)

    if os.path.isdir(normalized):
        return "created"

    raise RuntimeError(f"Failed to create file-server folder: {normalized}")


def ensure_show_manifest(show_root_path, requested_show_name):
    show_root = os.path.normpath(str(show_root_path or "").strip())
    if not show_root:
        raise RuntimeError("Cannot create show manifest because show_root_path was empty.")

    manifest_path = os.path.join(show_root, SHOW_MANIFEST_FILE_NAME)
    manifest_path = os.path.normpath(manifest_path)

    if os.path.isfile(manifest_path):
        log(f"Show manifest already exists: {manifest_path}")
        return "exists", manifest_path

    manifest_data = {
        "ShowName": str(requested_show_name or DEFAULT_SHOW_NAME).strip() or DEFAULT_SHOW_NAME,
    }

    os.makedirs(show_root, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest_data, handle, indent=2)
        handle.write("\n")

    if not os.path.isfile(manifest_path):
        raise RuntimeError(f"Failed to create show manifest: {manifest_path}")

    return "created", manifest_path


def create_file_server_structure(requested_show_name):
    """
    Creates missing file-server show root folders only if ShowFileServerPath exists
    in the settings file. Existing folders/files are left untouched.
    """
    show_root = get_saved_show_file_server_path()
    if not show_root:
        return {
            "file_server_enabled": False,
            "show_file_server_path": "",
            "created_file_server_folders": 0,
            "existing_file_server_folders": 0,
            "created_file_server_files": 0,
            "existing_file_server_files": 0,
        }

    folder_paths = build_file_server_folder_paths(show_root)

    created_folders = 0
    existing_folders = 0

    for folder_path in folder_paths:
        result = ensure_file_server_directory(folder_path)
        if result == "created":
            created_folders += 1
            log(f"Created file-server folder: {folder_path}")
        else:
            existing_folders += 1
            log(f"File-server folder already exists: {folder_path}")

    manifest_result, manifest_path = ensure_show_manifest(show_root, requested_show_name)
    if manifest_result == "created":
        created_files = 1
        existing_files = 0
        log(f"Created show manifest: {manifest_path}")
    else:
        created_files = 0
        existing_files = 1

    return {
        "file_server_enabled": True,
        "show_file_server_path": show_root,
        "created_file_server_folders": created_folders,
        "existing_file_server_folders": existing_folders,
        "created_file_server_files": created_files,
        "existing_file_server_files": existing_files,
        "show_manifest_path": manifest_path,
    }


# -----------------------------------------------------------------------------
# Scan / preview helpers
# -----------------------------------------------------------------------------

def scan_missing_items(show_name):
    """
    Useful if you later want a preview mode from Blueprint.
    Returns:
        dict
    """
    sanitized_show_name = sanitize_show_name(show_name)
    root_game_path, show_exists = find_existing_show_root_game_path(show_name, sanitized_show_name)
    show_folder_name = root_game_path.split("/")[-1]
    all_game_paths = build_all_game_paths(show_folder_name)

    missing_folder_count = 0
    missing_asset_count = 0

    if show_exists:
        log(f"Existing show detected during scan: {root_game_path}")
        return {
            "requested_show_name": show_name,
            "sanitized_show_name": sanitized_show_name,
            "root_game_path": root_game_path,
            "existing_show_detected": True,
            "total_target_folders": 0,
            "missing_folders": 0,
            "missing_assets": 0,
        }

    for folder_path in all_game_paths:
        if not unreal.EditorAssetLibrary.does_directory_exist(folder_path):
            missing_folder_count += 1

        asset_path = get_placeholder_asset_path(folder_path, root_game_path)
        if not unreal.EditorAssetLibrary.does_asset_exist(asset_path):
            missing_asset_count += 1

    return {
        "requested_show_name": show_name,
        "sanitized_show_name": sanitized_show_name,
        "root_game_path": root_game_path,
        "existing_show_detected": False,
        "total_target_folders": len(all_game_paths),
        "missing_folders": missing_folder_count,
        "missing_assets": missing_asset_count,
    }


# -----------------------------------------------------------------------------
# Main creation logic
# -----------------------------------------------------------------------------

def existing_show_summary(requested_show_name, sanitized_show_name, root_game_path, settings_path, settings_show_name):
    summary = {
        "requested_show_name": requested_show_name,
        "sanitized_show_name": sanitized_show_name,
        "root_game_path": root_game_path,
        "existing_show_detected": True,
        "skipped_structure_creation": True,
        "created_folders": 0,
        "existing_folders": 0,
        "created_assets": 0,
        "existing_assets": 0,
        "file_server_enabled": False,
        "show_file_server_path": "",
        "created_file_server_folders": 0,
        "existing_file_server_folders": 0,
        "created_file_server_files": 0,
        "existing_file_server_files": 0,
        "settings_path": settings_path,
        "settings_show_name": settings_show_name,
    }

    log("Existing show detected. Stopping after writing settings variable.")
    log("No Unreal folders, Unreal assets, file-server folders, or file-server files were created.")
    log("Done.")
    log("Summary:")
    log(f"  Requested Show Name: {summary['requested_show_name']}")
    log(f"  Sanitized Show Name: {summary['sanitized_show_name']}")
    log(f"  Existing Root Path: {summary['root_game_path']}")
    log(f"  Settings File: {summary['settings_path']}")
    log(f"  Settings show_name: {summary['settings_show_name']}")
    log(f"  Skipped structure creation: {summary['skipped_structure_creation']}")
    return summary


def create_new_show_structure(requested_show_name, sanitized_show_name, root_game_path, settings_path, settings_show_name):
    show_folder_name = root_game_path.split("/")[-1]
    all_game_paths = build_all_game_paths(show_folder_name)
    root_placeholder_asset_path = get_placeholder_asset_path(root_game_path, root_game_path)

    created_folders = 0
    existing_folders = 0
    created_assets = 0
    existing_assets = 0

    for folder_path in all_game_paths:
        folder_result = ensure_unreal_directory(folder_path)
        if folder_result == "created":
            created_folders += 1
            log(f"Created folder: {folder_path}")
        else:
            existing_folders += 1
            log(f"Folder already exists: {folder_path}")

        asset_result, asset_path = ensure_placeholder_blueprint(
            folder_game_path=folder_path,
            root_game_path=root_game_path,
        )
        if asset_result == "created":
            created_assets += 1
            log(f"Created placeholder Blueprint: {asset_path}")
        else:
            existing_assets += 1
            log(f"Placeholder Blueprint already exists: {asset_path}")

    file_server_summary = create_file_server_structure(requested_show_name)

    # Do not call EditorAssetLibrary.save_directory(root_game_path, recursive=True).
    # That can load/build/checkout a very large number of existing project assets.
    # Newly created placeholder assets are saved individually inside ensure_placeholder_blueprint().

    try:
        if created_assets > 0 and unreal.EditorAssetLibrary.does_asset_exist(root_placeholder_asset_path):
            unreal.EditorAssetLibrary.sync_browser_to_objects([root_placeholder_asset_path])
    except Exception as exc:
        log_warning(f"sync_browser_to_objects warning: {exc}")

    summary = {
        "requested_show_name": requested_show_name,
        "sanitized_show_name": sanitized_show_name,
        "root_game_path": root_game_path,
        "root_placeholder_asset_path": root_placeholder_asset_path,
        "existing_show_detected": False,
        "skipped_structure_creation": False,
        "total_target_folders": len(all_game_paths),
        "created_folders": created_folders,
        "existing_folders": existing_folders,
        "created_assets": created_assets,
        "existing_assets": existing_assets,
        "settings_path": settings_path,
        "settings_show_name": settings_show_name,
    }
    summary.update(file_server_summary)

    log("Done.")
    log("Summary:")
    log(f"  Requested Show Name: {summary['requested_show_name']}")
    log(f"  Sanitized Show Name: {summary['sanitized_show_name']}")
    log(f"  Root Path: {summary['root_game_path']}")
    log(f"  Root Placeholder: {summary['root_placeholder_asset_path']}")
    log(f"  Total Target Folders: {summary['total_target_folders']}")
    log(f"  Created Unreal folders: {summary['created_folders']}")
    log(f"  Existing Unreal folders: {summary['existing_folders']}")
    log(f"  Created placeholder Blueprints: {summary['created_assets']}")
    log(f"  Existing placeholder Blueprints: {summary['existing_assets']}")
    log(f"  Settings File: {summary['settings_path']}")
    log(f"  Settings show_name: {summary['settings_show_name']}")
    log(f"  File-server enabled: {summary['file_server_enabled']}")
    if summary["file_server_enabled"]:
        log(f"  Show File Server Path: {summary['show_file_server_path']}")
        log(f"  Created file-server folders: {summary['created_file_server_folders']}")
        log(f"  Existing file-server folders: {summary['existing_file_server_folders']}")
        log(f"  Created file-server files: {summary['created_file_server_files']}")
        log(f"  Existing file-server files: {summary['existing_file_server_files']}")
        log(f"  Show Manifest: {summary.get('show_manifest_path', '')}")

    return summary


def create_show_structure(requested_show_name):
    sanitized_show_name = sanitize_show_name(requested_show_name)
    root_game_path, existing_show_detected = find_existing_show_root_game_path(
        requested_show_name=requested_show_name,
        fallback_sanitized_show_name=sanitized_show_name,
    )

    log(f"Requested show name: {requested_show_name}")
    log(f"Sanitized show name: {sanitized_show_name}")
    log(f"Target game path: {root_game_path}")
    log(f"Existing show detected: {existing_show_detected}")

    settings_path, settings_show_name = write_show_name_setting(requested_show_name)

    if existing_show_detected:
        return existing_show_summary(
            requested_show_name=requested_show_name,
            sanitized_show_name=sanitized_show_name,
            root_game_path=root_game_path,
            settings_path=settings_path,
            settings_show_name=settings_show_name,
        )

    return create_new_show_structure(
        requested_show_name=requested_show_name,
        sanitized_show_name=sanitized_show_name,
        root_game_path=root_game_path,
        settings_path=settings_path,
        settings_show_name=settings_show_name,
    )


# -----------------------------------------------------------------------------
# Cleanup helper
# -----------------------------------------------------------------------------

def delete_all_placeholder_assets(show_name):
    """
    Deletes _showholder at the root and _folderholder in subfolders for a given show.
    """
    sanitized_show_name = sanitize_show_name(show_name)
    root_game_path, _existing_show_detected = find_existing_show_root_game_path(show_name, sanitized_show_name)
    show_folder_name = root_game_path.split("/")[-1]
    all_game_paths = build_all_game_paths(show_folder_name)

    deleted_count = 0

    for folder_path in all_game_paths:
        asset_path = get_placeholder_asset_path(folder_path, root_game_path)
        if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
            deleted = unreal.EditorAssetLibrary.delete_asset(asset_path)
            if deleted:
                deleted_count += 1
                log(f"Deleted placeholder Blueprint: {asset_path}")
            else:
                log_warning(f"Failed to delete placeholder Blueprint: {asset_path}")

    log(f"Deleted {deleted_count} placeholder Blueprints for show {root_game_path}")
    return deleted_count


# -----------------------------------------------------------------------------
# Entry point for Blueprint
# -----------------------------------------------------------------------------

def run(show_name):
    """
    Main entry point called from the Execute Python Script node.
    """
    try:
        requested_show_name = (show_name or "").strip()
        if not requested_show_name:
            requested_show_name = DEFAULT_SHOW_NAME

        return create_show_structure(requested_show_name)

    except Exception as exc:
        log_error(f"Failed to initialize show: {exc}")
        log_error(traceback.format_exc())
        raise
