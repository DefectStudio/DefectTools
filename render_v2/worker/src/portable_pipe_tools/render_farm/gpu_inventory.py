"""Read installed Windows graphics adapters and their dedicated video memory."""

import csv
import ctypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from uuid import UUID


_MAX_ADAPTERS = 32
_NVIDIA_VENDOR = 0x10DE
_DXGI_ADAPTER_FLAG_SOFTWARE = 2
_LOAD_LIBRARY_SEARCH_SYSTEM32 = 0x800


class _AdapterDescription(ctypes.Structure):
    # DXGI_ADAPTER_DESC1 uses SIZE_T for memory counts and LUID for adapter identity.
    _fields_ = [
        ("description", ctypes.c_wchar * 128),
        ("vendor_id", ctypes.c_uint),
        ("device_id", ctypes.c_uint),
        ("subsystem_id", ctypes.c_uint),
        ("revision", ctypes.c_uint),
        ("dedicated_video_memory", ctypes.c_size_t),
        ("dedicated_system_memory", ctypes.c_size_t),
        ("shared_system_memory", ctypes.c_size_t),
        ("adapter_luid", ctypes.c_uint32 * 2),
        ("flags", ctypes.c_uint),
    ]


def _adapter_record(name: str, vram_mib: int) -> dict[str, str | int] | None:
    model = " ".join(name.split())
    model = re.sub(r"^(?:NVIDIA )?(?:GeForce )?(?=RTX )", "", model, flags=re.IGNORECASE)
    if (not model or not model.isprintable() or len(model) > 200 or model.casefold() in {"[n/a]", "n/a", "unknown"}
            or not 0 < vram_mib <= 1_048_576):
        return None
    return {"model": model, "vram_mib": vram_mib}


def _nvidia_smi_path() -> str | None:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    program_files = Path(os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles", r"C:\Program Files"))
    for candidate in (
        system_root / "Sysnative" / "nvidia-smi.exe",
        system_root / "System32" / "nvidia-smi.exe",
        program_files / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe",
    ):
        if candidate.is_file():
            return str(candidate)
    return shutil.which("nvidia-smi.exe")


def _nvidia_adapters() -> list[dict[str, str | int]]:
    try:
        executable = _nvidia_smi_path()
        if not executable:
            return []
        result = subprocess.run(
            [executable, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, encoding="utf-8", errors="replace", check=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []

    adapters = []
    for line in result.stdout.splitlines():
        try:
            row = next(csv.reader([line], strict=True))
        except csv.Error:
            continue
        if len(row) != 2 or not re.fullmatch(r"[0-9]{1,7}", row[1].strip()):
            continue
        record = _adapter_record(row[0], int(row[1]))
        if record is not None:
            adapters.append(record)
            if len(adapters) == _MAX_ADAPTERS:
                break
    return adapters


def _dxgi_adapters() -> list[tuple[int, str, int]]:
    # A 32-bit SIZE_T cannot represent the dedicated memory of larger cards.
    if ctypes.sizeof(ctypes.c_size_t) < 8:
        return []
    try:
        dxgi = ctypes.WinDLL("dxgi.dll", winmode=_LOAD_LIBRARY_SEARCH_SYSTEM32)
        create_factory = dxgi.CreateDXGIFactory1
    except (AttributeError, OSError):
        return []

    create_factory.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    create_factory.restype = ctypes.c_long
    factory_iid = ctypes.create_string_buffer(UUID("770aae78-f26f-4dba-a829-253c83d1b387").bytes_le)
    # COM slots for IUnknown::Release, IDXGIFactory1::EnumAdapters1 and IDXGIAdapter1::GetDesc1.
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong)(2, "Release")
    enumerate_adapter = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(
        12, "EnumAdapters1"
    )
    get_description = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(_AdapterDescription))(10, "GetDesc1")

    factory = ctypes.c_void_p()
    if create_factory(factory_iid, ctypes.byref(factory)) != 0 or not factory:
        return []
    adapters = []
    try:
        for index in range(_MAX_ADAPTERS):
            adapter = ctypes.c_void_p()
            if enumerate_adapter(factory, index, ctypes.byref(adapter)) != 0 or not adapter:
                break
            try:
                desc = _AdapterDescription()
                if get_description(adapter, ctypes.byref(desc)) == 0 and not (desc.flags & _DXGI_ADAPTER_FLAG_SOFTWARE):
                    adapters.append((desc.vendor_id, desc.description, desc.dedicated_video_memory // 1024**2))
            finally:
                release(adapter)
    finally:
        release(factory)
    return adapters


def detect_gpus() -> list[dict[str, str | int]]:
    """Report available hardware inventory, without selecting an Unreal adapter."""
    if sys.platform != "win32":
        return []
    nvidia = _nvidia_adapters()
    adapters = list(nvidia)
    try:
        dxgi = _dxgi_adapters()
    except (OSError, ValueError):
        return adapters
    for vendor, name, vram_mib in dxgi:
        # DXGI can enumerate the same NVIDIA board through multiple logical adapters.
        if vendor == _NVIDIA_VENDOR and nvidia:
            continue
        record = _adapter_record(name, vram_mib)
        if record is not None:
            adapters.append(record)
    return adapters[:_MAX_ADAPTERS]
