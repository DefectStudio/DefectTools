"""Reuse suitable existing repositories or prepare a worker-owned checkout."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from itertools import chain
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from typing import Callable
from uuid import uuid4

from portable_pipe_tools.render_farm.project_catalog import ProjectDefinition
from portable_pipe_tools.render_farm.project_discovery import default_search_roots, editor_project_candidates, repository_candidates, repository_identity
from portable_pipe_tools.render_farm.unreal_runner import resolve_unreal_editor_cmd


class PreparationError(RuntimeError):
    pass


class PreparationCancelled(PreparationError):
    pass


@dataclass(frozen=True)
class PreparedProject:
    project: ProjectDefinition
    checkout: Path
    uproject: Path
    commit: str
    engine: Path


@contextmanager
def project_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise PreparationError("Another worker is already using this project workspace") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class ProjectWorkspace:
    def __init__(self, root: Path, *, progress: Callable[[str], None] = print,
                 cancelled: Callable[[], bool] = lambda: False,
                 timeout_seconds: float = 7200, cache_roots: tuple[Path, ...] = (),
                 discovery_roots: tuple[Path, ...] | None = None):
        self.root = Path(root).resolve()
        if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Preparation timeout must be a positive finite number")
        self.progress = progress
        self.cancelled = cancelled
        self.timeout_seconds = timeout_seconds
        self.cache_roots = cache_roots
        self.discovery_roots = default_search_roots() if discovery_roots is None else discovery_roots
        self.deadline = 0.0

    def check_cancelled(self):
        if self.cancelled():
            raise PreparationCancelled("Project preparation cancelled")
        if self.deadline and time.monotonic() >= self.deadline:
            raise PreparationError("Project preparation timed out")

    def run(self, args: list[str], cwd: Path, *, capture: bool = False) -> str:
        self.check_cancelled()
        logs = self.root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        log = logs / f"git-{uuid4().hex}.log"
        environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never",
                           GIT_LFS_SKIP_SMUDGE="1")
        if not capture:
            environment["GIT_LFS_FORCE_PROGRESS"] = "1"
        with log.open("wb") as output:
            process = subprocess.Popen(
                ["git", *args], cwd=cwd, env=environment, stdout=output,
                stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                start_new_session=os.name != "nt",
            )
            started = time.monotonic()
            next_update = started + 30
            try:
                while process.poll() is None:
                    self.check_cancelled()
                    if time.monotonic() >= next_update:
                        detail = ""
                        if args[:2] in (["lfs", "fetch"], ["lfs", "checkout"]):
                            try:
                                with log.open("rb") as reader:
                                    reader.seek(max(0, log.stat().st_size - 1200))
                                    lines = reader.read().decode("utf-8", errors="replace").splitlines()
                                detail = lines[-1][-300:] if lines else ""
                            except OSError:
                                pass
                        self.progress(detail or f"Git {' '.join(args[:2])} is working ({int(time.monotonic() - started)} seconds); log: {log}")
                        next_update = time.monotonic() + 30
                    time.sleep(0.15)
            except BaseException:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                raise
        if process.returncode:
            with log.open("rb") as stream:
                stream.seek(max(0, log.stat().st_size - 2500))
                detail = stream.read().decode("utf-8", errors="replace")
            raise PreparationError(f"Git {args[0]} failed; log: {log}\n{detail}")
        return log.read_text(encoding="utf-8", errors="replace").strip() if capture else ""

    @contextmanager
    def acquire(self, project: ProjectDefinition, *, engine: Path | None = None):
        self.root.mkdir(parents=True, exist_ok=True)
        with project_lock(self.root / ".locks" / f"{project.project_id}.lock"):
            self.deadline = time.monotonic() + self.timeout_seconds
            existing = self._discover(project)
            if existing is not None:
                lock_path = Path(self.run(["rev-parse", "--git-path", "render-worker.lock"], existing, capture=True))
                if not lock_path.is_absolute():
                    lock_path = existing / lock_path
                with project_lock(lock_path):
                    yield self._prepare_existing(project, existing, engine=engine)
            else:
                # Hold the lock until the caller's render/finalization is finished.
                yield self.prepare(project, engine=engine)

    def _discover(self, project: ProjectDefinition) -> Path | None:
        self.progress(f"Looking for an existing {project.project_id} repository")
        index_path = self.root / "discovered-projects.json"
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            index = {}
        if not isinstance(index, dict):
            index = {}
        remembered = index.get(project.project_id)
        roots = ((Path(remembered),) if isinstance(remembered, str) else ()) + tuple(self.discovery_roots)
        self.progress("Checking Unreal Editor and Epic Launcher project locations")
        candidates = chain(
            editor_project_candidates(excluded=(self.root,), check_cancelled=self.check_cancelled),
            repository_candidates(roots, excluded=(self.root,), check_cancelled=self.check_cancelled),
        )
        seen = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if not (candidate / project.uproject).is_file():
                continue
            if (candidate / ".git/render-worker.json").is_file():
                continue
            try:
                remote = self.run(["remote", "get-url", "origin"], candidate, capture=True)
                if repository_identity(remote) != repository_identity(project.repository):
                    continue
                branch = self.run(["branch", "--show-current"], candidate, capture=True)
                if branch != project.branch:
                    self.progress(f"Skipping {candidate}: it is on '{branch or 'detached HEAD'}', not '{project.branch}'")
                    continue
            except PreparationCancelled:
                raise
            except PreparationError:
                continue
            index[project.project_id] = str(candidate)
            temporary = index_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(index, indent=2), encoding="utf-8")
            temporary.replace(index_path)
            self.progress(f"Using existing project: {candidate}")
            return candidate
        return None

    def _prepare_existing(self, project: ProjectDefinition, checkout: Path, *, engine: Path | None):
        # Never change an existing checkout's branch or discard tracked edits.
        if self.run(["status", "--porcelain", "--untracked-files=no"], checkout, capture=True):
            raise PreparationError(f"Existing project has tracked local changes; preserving them: {checkout}")
        self.progress(f"Pulling latest {project.branch} in {checkout}")
        self.run(["pull", "--ff-only", "origin", project.branch], checkout)
        commit = self.run(["rev-parse", "HEAD"], checkout, capture=True)
        fetched = self.run(["rev-parse", "FETCH_HEAD^{commit}"], checkout, capture=True)
        if commit != fetched:
            raise PreparationError(f"Existing project has local commits beyond the remote; preserving them: {checkout}")
        uproject = (checkout / project.uproject).resolve()
        if not uproject.is_relative_to(checkout.resolve()):
            raise PreparationError("Project file resolves outside the existing checkout")
        selected_engine = resolve_unreal_editor_cmd({}, configured_path=engine, local_uproject=uproject)
        if project.submodules:
            self.run(["submodule", "update", "--init", "--recursive", "--depth", "1"], checkout)
        if project.lfs:
            self.progress("Updating current Git LFS assets")
            self.run(["lfs", "pull", "origin"], checkout)
            if project.submodules:
                self.run(["submodule", "foreach", "--recursive", "git lfs pull"], checkout)
        self.check_cancelled()
        self.progress(f"Project ready: {project.project_id} at {commit[:12]} ({checkout})")
        return PreparedProject(project, checkout, uproject, commit, selected_engine)

    def prepare(self, project: ProjectDefinition, *, engine: Path | None = None) -> PreparedProject:
        self.deadline = time.monotonic() + self.timeout_seconds
        self.check_cancelled()
        projects = self.root / "projects"
        projects.mkdir(parents=True, exist_ok=True)
        target = projects / project.project_id
        if not target.resolve().is_relative_to(self.root):
            raise PreparationError("Project workspace resolves outside the configured root")
        fresh = not target.exists()
        if fresh:
            staging = self.root / ".staging"
            staging.mkdir(exist_ok=True)
            checkout = self._recover_staging(staging, project)
            if checkout is None:
                checkout = staging / f"{project.project_id}-{uuid4().hex}"
                self.progress(f"Cloning {project.project_id} ({project.branch})")
                self.run(["clone", "-c", "core.longpaths=true", "--depth", "1", "--no-local", "--no-checkout", "--single-branch", "--branch", project.branch,
                          "--", project.repository, str(checkout)], self.root)
                self._write_marker(checkout, project, phase="cloned")
        else:
            checkout = target
            self._check_marker(checkout, project)
            status = self.run(["status", "--porcelain", "--untracked-files=all"], checkout, capture=True)
            if status:
                raise PreparationError(f"Worker checkout has local changes; preserving them: {checkout}")
            remote = self.run(["remote", "get-url", "origin"], checkout, capture=True)
            if remote != project.repository:
                raise PreparationError("Checkout origin differs from the approved project repository")

        self.progress(f"Updating {project.branch}")
        self.run(["fetch", "--prune", "origin", f"+refs/heads/{project.branch}:refs/remotes/origin/{project.branch}"], checkout)
        self.run(["checkout", project.branch], checkout)
        self.run(["pull", "--ff-only", "origin", project.branch], checkout)
        commit = self.run(["rev-parse", "HEAD"], checkout, capture=True)
        fetched = self.run(["rev-parse", "FETCH_HEAD^{commit}"], checkout, capture=True)
        if commit != fetched:
            raise PreparationError("Worker branch has local commits beyond the remote; preserving them")
        self.progress(f"Updated to {commit[:12]}")
        self._write_marker(checkout, project, phase="checkout")
        uproject = (checkout / project.uproject).resolve()
        if not uproject.is_relative_to(checkout.resolve()) or not uproject.is_file():
            raise PreparationError(f"Project file missing or outside checkout: {project.uproject}")
        self.progress("Finding the matching Unreal installation")
        selected_engine = resolve_unreal_editor_cmd({}, configured_path=engine, local_uproject=uproject)

        if project.submodules:
            self.progress("Updating project submodules")
            self.run(["submodule", "sync", "--recursive"], checkout)
            self.run(["submodule", "update", "--init", "--recursive", "--depth", "1"], checkout)
        if project.lfs:
            self._hydrate_lfs(checkout)
            if project.submodules:
                # Git runs this fixed command; no catalog-provided shell is used.
                self.run(["submodule", "foreach", "--recursive", "git lfs pull"], checkout)
        self.check_cancelled()
        self._write_marker(checkout, project)
        if fresh:
            checkout.rename(target)
            checkout = target
        self.progress(f"Project ready: {project.project_id} at {commit[:12]}")
        return PreparedProject(project, checkout, checkout / project.uproject, commit, selected_engine)

    def _recover_staging(self, staging: Path, project: ProjectDefinition) -> Path | None:
        for candidate in sorted(staging.glob(f"{project.project_id}-*"), reverse=True):
            if not candidate.resolve().is_relative_to(self.root):
                continue
            try:
                self._check_marker(candidate, project)
                marker = json.loads((candidate / ".git/render-worker.json").read_text(encoding="utf-8"))
            except PreparationError:
                continue
            if marker.get("phase") != "cloned":
                status = self.run(["status", "--porcelain", "--untracked-files=all"], candidate, capture=True)
                if status:
                    raise PreparationError(f"Interrupted checkout has local changes; preserving them: {candidate}")
            remote = self.run(["remote", "get-url", "origin"], candidate, capture=True)
            if remote != project.repository:
                raise PreparationError("Interrupted checkout origin differs from the project definition")
            self.progress(f"Resuming interrupted preparation of {project.project_id}")
            return candidate
        return None

    def _write_marker(self, checkout: Path, project: ProjectDefinition, *, phase="ready"):
        metadata = checkout / ".git" / "render-worker.json"
        temporary = metadata.with_suffix(".tmp")
        temporary.write_text(json.dumps({"project_id": project.project_id,
                                       "repository": project.repository,
                                       "revision": project.revision, "phase": phase}), encoding="utf-8")
        temporary.replace(metadata)

    def _check_marker(self, checkout: Path, project: ProjectDefinition):
        try:
            marker = json.loads((checkout / ".git" / "render-worker.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise PreparationError(f"Refusing to adopt an unmanaged checkout: {checkout}") from error
        if not isinstance(marker, dict) or marker.get("project_id") != project.project_id or marker.get("repository") != project.repository:
            raise PreparationError("Project definition does not match the existing managed checkout")

    def _hydrate_lfs(self, checkout: Path):
        self.progress("Inspecting Git LFS asset requirements")
        document = json.loads(self.run(["lfs", "ls-files", "--json"], checkout, capture=True))
        files = document.get("files", [])
        media = checkout / ".git" / "lfs" / "objects"
        seeded = 0
        for item in files:
            self.check_cancelled()
            oid = item["oid"]
            destination = media / oid[:2] / oid[2:4] / oid
            if destination.exists():
                continue
            for cache in self.cache_roots:
                candidate = Path(cache) / oid[:2] / oid[2:4] / oid
                if candidate.is_file() and candidate.stat().st_size == item["size"]:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        os.link(candidate, destination)
                    except OSError:
                        if shutil.disk_usage(checkout).free < item["size"] + 1024 ** 3:
                            raise PreparationError("Insufficient disk space to copy cached LFS assets")
                        shutil.copyfile(candidate, destination)
                    seeded += 1
                    break
        missing_bytes = sum(item["size"] for item in files if not (
            media / item["oid"][:2] / item["oid"][2:4] / item["oid"]
        ).exists())
        checkout_bytes = sum(item["size"] for item in files if not item.get("checkout"))
        required = missing_bytes + checkout_bytes + 1024 ** 3
        if shutil.disk_usage(checkout).free < required:
            raise PreparationError(f"Insufficient disk space; need about {required / 1024**3:.1f} GiB for assets and checkout")
        self.progress(f"LFS: {len(files)} assets, {seeded} reused from machine cache, {missing_bytes / 1024**3:.1f} GiB to download")
        self.run(["lfs", "fetch", "origin", "HEAD"], checkout)
        self.progress("Materializing project assets")
        self.run(["lfs", "checkout"], checkout)
        result = json.loads(self.run(["lfs", "ls-files", "--json"], checkout, capture=True))
        if any(not item.get("checkout") for item in result.get("files", [])):
            raise PreparationError("Project still contains unhydrated Git LFS pointers")
