"""Resource and settings locations for source launches and the portable EXE."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def settings_directory() -> Path:
    if is_frozen():
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        return local / "DefectRenderWorker"
    return resource_root() / "LocalSaveFiles"


def default_settings_path() -> Path:
    return settings_directory() / "worker_v2.json"


def default_catalog_path() -> Path:
    if is_frozen():
        adjacent = Path(sys.executable).parent / "projects.json"
        if adjacent.is_file():
            return adjacent
    return resource_root() / "projects.json"


def default_workspace() -> Path:
    return (Path.home() if is_frozen() else resource_root().parent) / "RenderWorkerWorkspace"


def prepare_external_programs() -> None:
    """Call after importing app dependencies, before launching Git or Unreal."""
    if is_frozen() and os.name == "nt":
        import ctypes
        # PyInstaller's DLL directory must not be inherited by Unreal/Git.
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        bundle = resource_root().resolve()
        paths = [entry for entry in os.environ.get("PATH", "").split(os.pathsep)
                 if entry and not Path(entry).resolve().is_relative_to(bundle)]
        os.environ["PATH"] = os.pathsep.join(paths)
    if shutil.which("git") or os.name != "nt":
        return
    import winreg
    candidates = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\GitForWindows", 0, winreg.KEY_READ | view) as key:
                    candidates.append(Path(winreg.QueryValueEx(key, "InstallPath")[0]) / "cmd")
            except OSError:
                continue
    candidates.extend([Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/cmd",
                       Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Programs/Git/cmd",
                       Path("D:/Program Files/Git/cmd")])
    for candidate in candidates:
        if (candidate / "git.exe").is_file():
            os.environ["PATH"] = str(candidate) + os.pathsep + os.environ.get("PATH", "")
            return
