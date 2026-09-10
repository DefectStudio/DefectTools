from __future__ import annotations

import ctypes
from pathlib import Path
import sys
import tkinter as tk


WINDOWS_APP_USER_MODEL_ID = "Defect.FarmRenderManager.1"
ASSET_FOLDER = Path(__file__).resolve().parents[1] / "assets"
ICON_PNG_PATH = ASSET_FOLDER / "farm_render_manager.png"
ICON_ICO_PATH = ASSET_FOLDER / "farm_render_manager.ico"


def configure_windows_app_identity() -> None:
    """Give Windows a stable identity so the taskbar uses our app icon."""
    if sys.platform != "win32":
        return
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        WINDOWS_APP_USER_MODEL_ID
    )


def apply_farm_render_manager_icon(root: tk.Tk) -> tk.PhotoImage | None:
    """Apply the local emoji icon and return the Tk image to keep it alive."""
    if sys.platform == "win32" and ICON_ICO_PATH.is_file():
        root.iconbitmap(default=str(ICON_ICO_PATH))
    if not ICON_PNG_PATH.is_file():
        return None
    icon_image = tk.PhotoImage(file=str(ICON_PNG_PATH))
    root.iconphoto(True, icon_image)
    return icon_image
