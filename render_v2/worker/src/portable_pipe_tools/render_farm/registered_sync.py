"""Update an explicitly registered checkout before rendering; never discover or clone it."""

from pathlib import Path
import shutil
import time

from portable_pipe_tools.app_runtime import prepare_external_programs
from portable_pipe_tools.render_farm.project_workspace import ProjectWorkspace, PreparationError

SYNC_POLICY = "latest_branch_git_pull_ff_only"


def sync_registered_project(uproject: Path, log_root: Path, *, progress=print,
                            cancelled=lambda: False, timeout_seconds=1800) -> str:
    """Caller holds the project lock through sync, runtime installation and render."""
    prepare_external_programs()
    if not shutil.which("git"):
        raise PreparationError("Install Git for Windows with Git LFS before rendering registered projects.")
    commands = ProjectWorkspace(log_root, progress=progress, cancelled=cancelled,
                                timeout_seconds=timeout_seconds, discovery_roots=())
    commands.deadline = time.monotonic() + timeout_seconds
    directory = Path(uproject).parent
    def run(args, cwd=None, capture=False):
        return commands.run(args, cwd or directory, capture=capture)
    root = Path(run(["rev-parse", "--show-toplevel"], capture=True))
    if not Path(uproject).resolve().is_relative_to(root.resolve()):
        raise PreparationError("Registered project is outside its Git checkout")
    directory = root
    branch = run(["branch", "--show-current"], capture=True)
    if not branch:
        raise PreparationError("Project checkout has detached HEAD. Select its render branch in Anchorpoint before rendering.")
    upstream = run(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], capture=True)
    changes = run(["status", "--porcelain", "--untracked-files=no", "--ignore-submodules=none"], capture=True)
    if changes:
        raise PreparationError("Project or submodule has local changes; preserving them and refusing to render. "
                               + " | ".join(changes.splitlines()[:5]))
    run(["lfs", "version"])
    progress(f"Updating registered project: git pull --ff-only ({branch} from {upstream})")
    run(["pull", "--ff-only", "--no-rebase", "--recurse-submodules=no"])
    commit = run(["rev-parse", "HEAD"], capture=True)
    remote_commit = run(["rev-parse", "@{upstream}"], capture=True)
    if commit != remote_commit:
        raise PreparationError("Project has local commits beyond its upstream. Resolve them in Anchorpoint before rendering.")
    progress("Updating project submodules to the versions recorded by the project")
    run(["submodule", "sync", "--recursive"])
    run(["submodule", "update", "--init", "--recursive", "--checkout", "--depth", "1"])
    progress("Downloading current Git LFS assets")
    run(["lfs", "pull", "--include=", "--exclude="])
    run(["submodule", "foreach", "--recursive", "git lfs pull --include= --exclude="])
    if run(["status", "--porcelain", "--untracked-files=no", "--ignore-submodules=none"], capture=True):
        raise PreparationError("Project has tracked changes after updating; rendering was not started.")
    commands.check_cancelled()
    if not Path(uproject).is_file():
        raise PreparationError("The registered .uproject was removed by the update. Update its registration before rendering.")
    progress(f"Project update complete: {branch} at {commit[:12]}")
    return commit
