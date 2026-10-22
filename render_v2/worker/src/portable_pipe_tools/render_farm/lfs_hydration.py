"""Plan LFS hydration around verified working files rather than cache copies."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import sys
import time
from uuid import uuid4

from portable_pipe_tools.render_farm.project_workspace import PreparationError, InsufficientDiskSpace
from portable_pipe_tools.render_farm.lfs_pointer_filter import _POINTER

DISK_RESERVE_BYTES = 1024 ** 3


def registered_git_config():
    helper = Path(__file__).with_name("lfs_pointer_filter.py").resolve().as_posix()
    command = f"{shlex.quote(Path(sys.executable).as_posix())} {shlex.quote(helper)}"
    return {"filter.lfs.process": command + " --process", "filter.lfs.clean": command,
            "lfs.fetchrecentalways": "false"}


def _existing_parent(path):
    path = Path(path).resolve()
    while not path.exists():
        parent = path.parent
        if parent == path:
            raise PreparationError(f"Cannot inspect disk space at {path}")
        path = parent
    return path


def check_disk_space(requirements, *, reserve_bytes=DISK_RESERVE_BYTES):
    """Sum allocations sharing a volume, including logs, before any downloads."""
    volumes = {}
    for path, required in requirements:
        existing = _existing_parent(path)
        key = existing.stat().st_dev
        entry = volumes.setdefault(key, [existing, 0])
        entry[1] += required
    for path, required in volumes.values():
        free = shutil.disk_usage(path).free
        if free < required + reserve_bytes:
            raise InsufficientDiskSpace(
                f"Insufficient disk space on {path}: need {(required + reserve_bytes) / 1024**3:.2f} GiB "
                f"including a {reserve_bytes / 1024**3:.0f} GiB reserve; "
                f"only {free / 1024**3:.2f} GiB is free. Automatic rendering must pause until space is available."
            )


def _file_matches(path, oid, size, check_cancelled):
    try:
        before = path.stat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(before.st_mode) or before.st_size != size:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            check_cancelled()
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise PreparationError(f"Asset changed while being verified: {path}")
    return digest.hexdigest() == oid


def _placeholder_or_missing(path, oid):
    if not path.exists():
        return True
    if not path.is_file() or path.stat().st_size > 1024:
        return False
    content = path.read_bytes()
    return bool(_POINTER.fullmatch(content) and f"oid sha256:{oid}\n".encode() in content)


@dataclass
class Asset:
    checkout: Path
    path: Path
    name: str
    oid: str
    size: int
    media: Path
    native_checkout: bool = False
    git_index_verified: bool = False

    @property
    def cached(self):
        return self.media / self.oid[:2] / self.oid[2:4] / self.oid


def _assets(run, checkout, *, progress=lambda message: None, check_cancelled=lambda: None,
            git_verified=False):
    check_cancelled()
    progress(f"Reading Git LFS asset metadata: {checkout}")
    output = run(["lfs", "ls-files", "--json"], cwd=checkout, capture=True)
    check_cancelled()
    document = json.loads(output)
    check_cancelled()
    files = document.get("files", [])
    if not files:
        return []
    index_verified = set()
    if git_verified:
        # Status intentionally ignores assume-unchanged and skip-worktree files.
        # Only ordinary cached (H) entries can inherit its verification. Lowercase
        # assume-unchanged tags and S/s skip-worktree tags need a content check.
        flags = run(["ls-files", "-v", "-z"], cwd=checkout, capture=True)
        check_cancelled()
        index_verified = {record[2:] for record in flags.split("\0") if record.startswith("H ")}
    environment = run(["lfs", "env"], cwd=checkout, capture=True)
    media = next((line.partition("=")[2] for line in environment.splitlines()
                  if line.startswith("LocalMediaDir=")), "")
    if not media or not Path(media).is_absolute():
        raise PreparationError("Git LFS did not report its asset storage location")
    checkout_root = checkout.resolve()
    assets = []
    last_progress = time.monotonic()
    for index, item in enumerate(files):
        check_cancelled()
        name, oid, size = item["name"], item["oid"], item["size"]
        relative = PurePosixPath(name)
        path = (checkout / name).resolve()
        if (relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(checkout_root)
                or not re.fullmatch("[0-9a-f]{64}", oid) or type(size) is not int or size < 0):
            raise PreparationError("Unsafe or invalid Git LFS asset metadata")
        assets.append(Asset(checkout, path, name, oid, size, Path(media), item.get("checkout") is True,
                            name in index_verified))
        if time.monotonic() - last_progress >= 30:
            progress(f"Reading Git LFS metadata: {index + 1}/{len(files)} assets")
            last_progress = time.monotonic()
    return assets


def _copy_verified_asset(source, asset, check_cancelled):
    if not _placeholder_or_missing(asset.path, asset.oid):
        raise PreparationError(f"Preserving an asset changed during preparation: {asset.path}")
    asset.path.parent.mkdir(parents=True, exist_ok=True)
    temporary = asset.path.with_name(f".{asset.path.name}.worker-lfs-{uuid4().hex}.tmp")
    original_mode = asset.path.stat().st_mode if asset.path.exists() else None
    digest = hashlib.sha256()
    copied = 0
    try:
        with source.open("rb") as reader, temporary.open("xb") as writer:
            while chunk := reader.read(4 * 1024 * 1024):
                check_cancelled()
                writer.write(chunk)
                digest.update(chunk)
                copied += len(chunk)
        if copied != asset.size or digest.hexdigest() != asset.oid:
            raise PreparationError(f"Cached/local asset changed or is corrupt: {source}")
        if not _placeholder_or_missing(asset.path, asset.oid):
            raise PreparationError(f"Preserving an asset changed during preparation: {asset.path}")
        if original_mode is not None:
            asset.path.chmod(original_mode | stat.S_IWRITE)
        os.replace(temporary, asset.path)
        if original_mode is not None:
            asset.path.chmod(original_mode)
    finally:
        if temporary.exists():
            temporary.unlink()


def hydrate_registered_assets(run, checkouts, log_root, *, progress, check_cancelled,
                              monitor_paths=lambda paths: None, git_verified=False):
    """Reuse clean Git worktree assets, hashing only content Git has not verified.

    ``git_verified`` is reserved for callers that have checked the worktree and
    index against the required revision, including submodules. Native LFS's
    checkout flag, an ordinary index entry, and a regular file of the expected
    size then identify hydrated assets. Files Git is told to ignore still need
    content verification, as do small files whose size could match a pointer.
    Sources are always hashed while copying into any missing working file.
    """
    all_assets = []
    for checkout in checkouts:
        all_assets.extend(_assets(run, checkout, progress=progress, check_cancelled=check_cancelled,
                                  git_verified=git_verified))
    monitor_paths(tuple({asset.media for asset in all_assets}))
    verified = {}
    pending = []
    last_progress = time.monotonic()
    phase = f"Checking {len(all_assets)} local LFS assets"
    progress(phase + (" using Git's verified working tree" if git_verified else " by content"))

    def check_progress():
        nonlocal last_progress
        check_cancelled()
        if time.monotonic() - last_progress >= 30:
            progress(phase)
            last_progress = time.monotonic()

    for index, asset in enumerate(all_assets):
        phase = f"Checking local LFS asset {index + 1}/{len(all_assets)}: {asset.name}"
        check_progress()
        # A successful Git status/index check is the authority for unchanged
        # full assets. Avoid rereading the entire project merely to hash it a
        # second time, or recreating cache copies of those complete files.
        try:
            info = (asset.path.stat()
                    if git_verified and asset.native_checkout and asset.git_index_verified and asset.size > 1024
                    else None)
        except FileNotFoundError:
            info = None
        git_matches = info is not None and stat.S_ISREG(info.st_mode) and info.st_size == asset.size
        if git_matches or _file_matches(asset.path, asset.oid, asset.size, check_progress):
            verified.setdefault(asset.oid, asset.path)
        elif _placeholder_or_missing(asset.path, asset.oid):
            pending.append(asset)
        else:
            raise PreparationError(f"LFS asset has local changes; preserving it and refusing to render: {asset.path}")
    downloads = {}
    sources = {}
    for asset in pending:
        phase = f"Checking cached LFS asset: {asset.name}"
        check_progress()
        source = verified.get(asset.oid)
        if source is None and asset.cached.exists():
            if not _file_matches(asset.cached, asset.oid, asset.size, check_progress):
                raise PreparationError(f"Git LFS cached asset is corrupt; refusing to reuse or repeatedly download it: {asset.cached}")
            source = asset.cached
        if source is None:
            # LFS include expressions are glob patterns separated by commas.
            # Refuse ambiguous expressions rather than downloading extra assets.
            if any(character in asset.name for character in ",*?[]\\\n\r"):
                raise PreparationError(f"Cannot safely target this LFS asset for download: {asset.name}")
            key = (asset.checkout, asset.oid)
            if key not in downloads:
                downloads[key] = asset
            source = asset.cached
        sources[id(asset)] = source
    def remaining_requirements():
        return ([(log_root, 0)]
                + [(asset.media, asset.size) for asset in downloads.values()
                   if not asset.cached.is_file() or asset.cached.stat().st_size != asset.size]
                + [(asset.path.parent, asset.size) for asset in pending])
    check_disk_space(remaining_requirements())
    download_bytes = sum(asset.size for asset in downloads.values())
    progress(f"LFS: {len(all_assets) - len(pending)} verified local assets reused; "
             f"{len(pending)} assets to materialize; {download_bytes / 1024**3:.2f} GiB to download")
    for checkout in checkouts:
        selected = [asset for asset in downloads.values() if asset.checkout == checkout]
        batch = []
        length = 0
        for asset in [*selected, None]:
            if batch and (asset is None or length + len(asset.name) + 2 > 6000):
                check_disk_space(remaining_requirements())
                run(["lfs", "fetch", "--include=" + ",".join("/" + item.name for item in batch), "--exclude="], cwd=checkout)
                batch, length = [], 0
            if asset is not None:
                batch.append(asset)
                length += len(asset.name) + 2
    for asset in pending:
        phase = f"Restoring LFS asset: {asset.name}"
        check_progress()
        check_disk_space([(log_root, 0), (asset.path.parent, asset.size)])
        _copy_verified_asset(sources[id(asset)], asset, check_progress)
    return pending
