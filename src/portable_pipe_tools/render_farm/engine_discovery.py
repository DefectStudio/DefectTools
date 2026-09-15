"""Find installed Unreal builds without requiring their default drive location."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re


_VERSION = re.compile(r"^(\d+\.\d+)(?:\.\d+)?$")


@dataclass(frozen=True)
class EngineInstallation:
    association: str
    root: Path

    @property
    def executable(self) -> Path:
        return self.root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"


def _launcher_installations() -> list[EngineInstallation]:
    manifest = (
        Path(os.environ.get("ProgramData") or r"C:\ProgramData")
        / "Epic"
        / "UnrealEngineLauncher"
        / "LauncherInstalled.dat"
    )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    entries = document.get("InstallationList", []) if isinstance(document, dict) else []
    if not isinstance(entries, list):
        return []
    installations = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("AppName")
        location = entry.get("InstallLocation")
        if (
            isinstance(name, str)
            and name.startswith("UE_")
            and _VERSION.fullmatch(name[3:])
            and isinstance(location, str)
            and location.strip()
        ):
            installations.append(EngineInstallation(name[3:], Path(location)))
    return installations


def _registry_installations() -> list[EngineInstallation]:
    try:
        import winreg
    except ImportError:
        return []

    installations = []
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Epic Games\Unreal Engine\Builds"
        ) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                association, location, _ = winreg.EnumValue(key, index)
                if isinstance(location, str) and location.strip():
                    installations.append(EngineInstallation(association, Path(location)))
    except OSError:
        pass

    # Registry views can differ when the worker runs with a 32-bit Python.
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\EpicGames\Unreal Engine",
                0,
                winreg.KEY_READ | view,
            ) as key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    association = winreg.EnumKey(key, index)
                    try:
                        with winreg.OpenKey(key, association) as child:
                            location, _ = winreg.QueryValueEx(child, "InstalledDirectory")
                        if isinstance(location, str) and location.strip():
                            installations.append(
                                EngineInstallation(association, Path(location))
                            )
                    except OSError:
                        continue
        except OSError:
            continue
    return installations


def _matches_installed_version(installation: EngineInstallation, version: str) -> bool:
    """Reject stale registrations pointing at a different or unreadable build."""
    metadata = installation.root / "Engine" / "Build" / "Build.version"
    try:
        document = json.loads(metadata.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        # Older/custom installs may not carry this file. The registration still
        # supplies the association; custom build identity needs an explicit match.
        return True
    except (OSError, ValueError):
        return False
    if not isinstance(document, dict):
        return False
    return f"{document.get('MajorVersion')}.{document.get('MinorVersion')}" == version


def path_engine_matches_versions(executable: Path, versions: Iterable[str]) -> bool:
    """PATH has no registered association, so require actual build metadata."""
    if len(executable.parents) < 4 or not executable.is_file():
        return False
    installation = EngineInstallation("", executable.parents[3])
    if not (installation.root / "Engine" / "Build" / "Build.version").is_file():
        return False
    return any(_matches_installed_version(installation, version) for version in versions)


def find_installed_unreal_editor(
    versions: Iterable[str], *, association: str = ""
) -> Path | None:
    """Resolve project association first, then requested major/minor versions.

    Only existing executables are returned. Discovery does not install engines,
    change associations, or execute any discovered programs.
    """
    versions = list(dict.fromkeys(versions))
    program_files = Path(os.environ.get("ProgramFiles") or r"C:\Program Files")
    installations = [
        EngineInstallation(version, program_files / "Epic Games" / f"UE_{version}")
        for version in versions
        if _VERSION.fullmatch(version)
    ]
    installations.extend(_launcher_installations())
    installations.extend(_registry_installations())

    # A GUID or custom build name must resolve to that registered build, not an
    # unrelated launcher build whose version happens to be the same.
    if association and not _VERSION.fullmatch(association):
        return next(
            (
                item.executable
                for item in installations
                if item.association.casefold() == association.casefold()
                and item.executable.is_file()
            ),
            None,
        )

    for version in versions:
        for item in installations:
            match = _VERSION.fullmatch(item.association)
            if (
                match
                and match.group(1) == version
                and item.executable.is_file()
                and _matches_installed_version(item, version)
            ):
                return item.executable
    return None
