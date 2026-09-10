# Build on Windows with the pinned build environment.
from pathlib import Path
import sys

root = Path(SPECPATH).parent
datas = [(str(root / "projects.json"), ".")]
for path in (root / "unreal").rglob("*"):
    if path.is_file() and path.suffix in {".py", ".uplugin"}:
        datas.append((str(path), str(path.parent.relative_to(root))))
license_file = Path(sys.base_prefix) / "LICENSE.txt"
if license_file.is_file():
    datas.append((str(license_file), "licenses/Python"))

a = Analysis([str(root / "packaging/worker_entry.py")], pathex=[str(root / "src")],
             binaries=[], datas=datas, hiddenimports=[], hookspath=[], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="RenderWorker",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, uac_admin=False)
