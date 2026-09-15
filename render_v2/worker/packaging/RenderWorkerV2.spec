# Both modes use the same entry point and explicit resource allowlist.
from pathlib import Path
import os
import sys

root = Path(SPECPATH).parent
datas = []
for directory, suffixes in (("unreal/RenderWorkerRuntime", {".py", ".uplugin"}), ("spriteImages", {".png"})):
    for path in (root / directory).rglob("*"):
        if path.is_file() and path.suffix in suffixes:
            datas.append((str(path), str(path.parent.relative_to(root))))
license_file = Path(sys.base_prefix) / "LICENSE.txt"
if license_file.is_file():
    datas.append((str(license_file), "licenses/Python"))
folder = os.environ.get("RENDER_WORKER_BUILD_MODE") == "folder"
a = Analysis([str(root / "packaging/v2_entry.py")], pathex=[str(root / "src")],
             binaries=[], datas=datas, hiddenimports=[], hookspath=[], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
options = dict(name="RenderWorkerV2", debug=False, bootloader_ignore_signals=False,
               strip=False, upx=False, console=False, disable_windowed_traceback=False, uac_admin=False,
               version=str(root / "packaging/version_info.txt"))
if folder:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **options)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RenderWorkerV2")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **options)
