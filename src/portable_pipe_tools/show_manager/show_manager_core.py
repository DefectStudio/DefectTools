from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import re


SCHEMA_VERSION = "0.1.0"
FOLDER_TEMPLATE_VERSION = "0.1.1"
PIPELINE_TOOL = "PortablePipeTools"
PIPELINE_TOOL_VERSION = "0.1.0"

EXAMPLE_DATE_FOLDER = "20260101_ExampleFolder"
EXAMPLE_SEQUENCE = "XXX"
EXAMPLE_SHOT = "XXX_000_0050"
EXAMPLE_RENDER = "XXX_000_0050_beauty_v001"


BASE_RELATIVE_FOLDERS: tuple[str, ...] = (
    "_input/client/20260101_ExampleFolder",
    "_input/misc/20260101_ExampleFolder",
    "_input/media_shuttle",

    "_output/edit/20260101_ExampleFolder",
    "_output/previs/20260101_ExampleFolder",
    "_output/client/20260101_ExampleFolder",

    "edit/davinci",
    "edit/edit_assets",

    "reference/20260101_ExampleFolder",

    "sequences/XXX/_output",

    "sequences/XXX/XXX_000_0050/anim/_output",
    "sequences/XXX/XXX_000_0050/anim/maya",

    "sequences/XXX/XXX_000_0050/fx/_output",
    "sequences/XXX/XXX_000_0050/fx/houdini",

    "sequences/XXX/XXX_000_0050/lite/_output",
    "sequences/XXX/XXX_000_0050/lite/unreal/_output/XXX_000_0050_beauty_v001",
    "sequences/XXX/XXX_000_0050/lite/unreal/_output/_hero",

    "sequences/XXX/XXX_000_0050/lvl/_output",
    "sequences/XXX/XXX_000_0050/lvl/unreal",
    "sequences/XXX/XXX_000_0050/lvl/maya",
    "sequences/XXX/XXX_000_0050/lvl/blender",

    "sequences/XXX/XXX_000_0050/comp/_output",
    "sequences/XXX/XXX_000_0050/comp/nuke",
    "sequences/XXX/XXX_000_0050/comp/natron",
    "sequences/XXX/XXX_000_0050/comp/davinci",

    "sequences/XXX/XXX_000_0050/mesh/_output",
    "sequences/XXX/XXX_000_0050/mesh/maya",
    "sequences/XXX/XXX_000_0050/mesh/blender",
    "sequences/XXX/XXX_000_0050/mesh/zbrush",

    "sequences/XXX/XXX_000_0050/_output",
    "sequences/XXX/XXX_000_0050/reference",
)


ASSET_EXAMPLE_FOLDERS: tuple[str, ...] = (
    "chr_ExampleCharacter",
    "prp_ExampleProp",
    "vhl_ExampleVehicle",
    "lvl_ExampleEnvironment",
    "fx_ExampleFX",
)


ASSET_DEPARTMENT_FOLDERS: tuple[str, ...] = (
    "_output",
    "anim",
    "rig",
    "fx",
    "lite",
    "lvl",
    "comp",
    "mesh",
    "reference",
)


ASSET_SOFTWARE_FOLDERS: tuple[str, ...] = (
    "_output",
    "unreal",
    "maya",
    "blender",
    "substance",
    "houdini",
    "nuke",
    "davinci",
    "katana",
    "zbrush",
    "natron",
    "emberliquigen",
)


@dataclass(frozen=True)
class ShowManagerResult:
    show_root: Path
    manifest_path: Path
    created_folders: list[Path]
    existing_folders: list[Path]
    missing_folders: list[Path]
    messages: list[str]


def sanitize_show_name(raw_show_name: str) -> str:
    """
    Convert a user-entered show name into a file-server-safe show folder name.

    Example:
        "Nightfall" -> "nightfall"
        "My Cool Show" -> "my_cool_show"
    """
    value = raw_show_name.strip().lower()
    value = re.sub(r"[\s\-]+", "_", value)
    value = re.sub(r"[^a-z0-9_]", "", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")

    if not value:
        raise ValueError("Show name is empty after sanitizing.")

    return value


def get_all_relative_folders() -> tuple[str, ...]:
    """
    Return every folder that Show Manager v0.1 expects to create.

    Asset examples intentionally include broad department/software examples
    so artists can see the intended folder shape immediately.
    """
    folders: list[str] = list(BASE_RELATIVE_FOLDERS)

    for asset_name in ASSET_EXAMPLE_FOLDERS:
        asset_root = f"assets/{asset_name}"
        folders.append(asset_root)

        for department_name in ASSET_DEPARTMENT_FOLDERS:
            department_root = f"{asset_root}/{department_name}"
            folders.append(department_root)

            # Avoid creating odd paths like:
            # assets/chr_ExampleCharacter/_output/_output
            if department_name == "_output":
                continue

            for software_name in ASSET_SOFTWARE_FOLDERS:
                folders.append(f"{department_root}/{software_name}")

    return tuple(folders)


def get_show_root(dropbox_root: str | Path, raw_show_name: str) -> Path:
    root = Path(dropbox_root).expanduser()
    show_name = sanitize_show_name(raw_show_name)
    return root / show_name


def get_manifest_path(show_root: Path) -> Path:
    return show_root / "_show_manifest.json"


def build_manifest(show_name: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "ShowName": show_name,
        "FolderTemplateVersion": FOLDER_TEMPLATE_VERSION,
        "CreatedUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "PipelineTool": PIPELINE_TOOL,
        "PipelineToolVersion": PIPELINE_TOOL_VERSION,
    }


def get_expected_folder_paths(show_root: Path) -> list[Path]:
    return [show_root / relative_path for relative_path in get_all_relative_folders()]


def preview_show(dropbox_root: str | Path, raw_show_name: str) -> list[str]:
    show_root = get_show_root(dropbox_root, raw_show_name)
    show_name = show_root.name
    manifest_path = get_manifest_path(show_root)

    lines = [
        "PREVIEW",
        "-------",
        f"Dropbox/File Server Root: {Path(dropbox_root)}",
        f"Sanitized Show Name: {show_name}",
        f"Show Root: {show_root}",
        f"Manifest: {manifest_path}",
        "",
        "Folders that will exist:",
    ]

    for folder_path in get_expected_folder_paths(show_root):
        lines.append(f"  {folder_path}")

    return lines


def create_show(dropbox_root: str | Path, raw_show_name: str) -> ShowManagerResult:
    root = Path(dropbox_root).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Dropbox/File Server root does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Dropbox/File Server root is not a folder: {root}")

    show_root = get_show_root(root, raw_show_name)
    show_name = show_root.name
    manifest_path = get_manifest_path(show_root)

    created_folders: list[Path] = []
    existing_folders: list[Path] = []
    messages: list[str] = []

    all_folder_paths = [show_root, *get_expected_folder_paths(show_root)]

    for folder_path in all_folder_paths:
        if folder_path.exists():
            existing_folders.append(folder_path)
        else:
            folder_path.mkdir(parents=True, exist_ok=True)
            created_folders.append(folder_path)

    if manifest_path.exists():
        messages.append(f"Manifest already exists. Did not overwrite: {manifest_path}")
    else:
        manifest_data = build_manifest(show_name)
        manifest_path.write_text(
            json.dumps(manifest_data, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        messages.append(f"Wrote manifest: {manifest_path}")

    missing_folders = [
        folder_path
        for folder_path in all_folder_paths
        if not folder_path.exists()
    ]

    messages.append(f"Show root: {show_root}")
    messages.append(f"Created folders: {len(created_folders)}")
    messages.append(f"Already existing folders: {len(existing_folders)}")
    messages.append(f"Missing folders after create: {len(missing_folders)}")

    return ShowManagerResult(
        show_root=show_root,
        manifest_path=manifest_path,
        created_folders=created_folders,
        existing_folders=existing_folders,
        missing_folders=missing_folders,
        messages=messages,
    )


def validate_show(dropbox_root: str | Path, raw_show_name: str) -> ShowManagerResult:
    show_root = get_show_root(dropbox_root, raw_show_name)
    manifest_path = get_manifest_path(show_root)

    expected_folders = [show_root, *get_expected_folder_paths(show_root)]

    existing_folders = [
        folder_path
        for folder_path in expected_folders
        if folder_path.exists()
    ]

    missing_folders = [
        folder_path
        for folder_path in expected_folders
        if not folder_path.exists()
    ]

    messages: list[str] = [
        "VALIDATION",
        "----------",
        f"Show root: {show_root}",
        f"Manifest: {manifest_path}",
    ]

    if manifest_path.exists():
        messages.append("[OK] Manifest exists.")
    else:
        messages.append("[MISSING] Manifest is missing.")

    if missing_folders:
        messages.append("")
        messages.append("Missing folders:")
        for folder_path in missing_folders:
            messages.append(f"  {folder_path}")
    else:
        messages.append("[OK] All expected folders exist.")

    messages.append("")
    messages.append(f"Existing folders: {len(existing_folders)}")
    messages.append(f"Missing folders: {len(missing_folders)}")

    return ShowManagerResult(
        show_root=show_root,
        manifest_path=manifest_path,
        created_folders=[],
        existing_folders=existing_folders,
        missing_folders=missing_folders,
        messages=messages,
    )
