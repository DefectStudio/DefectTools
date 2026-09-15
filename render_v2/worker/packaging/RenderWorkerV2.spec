# Both modes use the same entry point and explicit resource allowlist.
from pathlib import Path
import os
import json
import sys
from urllib.parse import urlparse

root = Path(SPECPATH).parent
datas = []
profile_path = Path(os.environ["RENDER_WORKER_COMPANY_CONNECTION"])
profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
company = {key: str(profile.get(key) or "").strip() for key in ("api_url", "worker_token")}
parsed = urlparse(company["api_url"])
if (not company["worker_token"] or not parsed.hostname or parsed.username or parsed.password
        or parsed.hostname == "defect-farm-api.twilight-tooth-7b7c.workers.dev"
        or not (parsed.scheme == "https" or parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"})):
    raise ValueError("Build requires a valid separate V2 service URL and worker credential.")
# Only worker-scoped connection data belongs in the internal distribution.
company_resource = root / "build/company-profile/worker_company_connection.json"
company_resource.parent.mkdir(parents=True, exist_ok=True)
company_resource.write_text(json.dumps(company), encoding="utf-8")
datas.append((str(company_resource), "."))
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
