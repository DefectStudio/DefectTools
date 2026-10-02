"""Update an explicitly registered checkout before rendering; never discover or clone it."""

from pathlib import Path, PurePosixPath
import shutil
import time

from portable_pipe_tools.app_runtime import prepare_external_programs
from portable_pipe_tools.render_farm.project_workspace import ProjectWorkspace, PreparationError

SYNC_POLICY = "latest_branch_git_pull_ff_only"


def _check_local_changes(run, directory):
    # A clean submodule at a different commit needs the normal pinned update,
    # not a refusal. Check the parent's index separately so ignoring submodule
    # worktree differences never hides an intentionally staged gitlink change.
    changes = run(["status", "--porcelain", "--untracked-files=no", "--ignore-submodules=all"], capture=True)
    staged = run(["diff", "--cached", "--name-only", "--ignore-submodules=none"], capture=True)
    if changes or staged:
        raise PreparationError("Project or submodule has local changes; preserving them and refusing to render. "
                               + " | ".join((changes or staged).splitlines()[:5]))
    submodule_changes = run(["submodule", "foreach", "--quiet", "--recursive",
                            'changes=$(git status --porcelain --untracked-files=no --ignore-submodules=all) || exit; '
                            'staged=$(git diff --cached --name-only --ignore-submodules=none) || exit; '
                            'if test -n "$changes$staged"; then '
                            'printf "Submodule %s has local changes\\n%s\\n%s\\n" "$displaypath" "$changes" "$staged"; fi'],
                           capture=True)
    if submodule_changes:
        raise PreparationError("Project or submodule has local changes; preserving them and refusing to render. "
                               + " | ".join(submodule_changes.splitlines()[:5]))
    # An ancestor checkout can change a nested module's target pin. Protect
    # every initialized descendant of a moving ancestor, even when its HEAD
    # currently matches its old pin. Aligned shallow pins need no remote proof.
    metadata = run(["submodule", "foreach", "--quiet", "--recursive",
                    'current=$(git rev-parse HEAD) || exit; '
                    'printf "module\\000%s\\000%s\\000%s\\000" "$displaypath" "$sha1" "$current"'], capture=True)
    fields = metadata.split("\0")[:-1] if metadata else []
    if len(fields) % 4 or any(fields[index] != "module" for index in range(0, len(fields), 4)):
        raise PreparationError("Could not safely inspect project submodules; rendering was not started.")
    modules = [(PurePosixPath(fields[index + 1]), fields[index + 2], fields[index + 3])
               for index in range(0, len(fields), 4)]
    moving = {path for path, pinned, current in modules if current != pinned}
    for path, pinned, current in modules:
        if path not in moving and not any(parent in moving for parent in path.parents):
            continue
        checkout = directory / str(path)
        if not checkout.resolve().is_relative_to(directory.resolve()):
            raise PreparationError("Submodule resolves outside the project checkout; rendering was not started.")
        # A containing remote-tracking ref proves this commit was fetched from
        # a remote. Unknown/unpublished commits stay in place for manual review.
        published = run(["for-each-ref", f"--contains={current}", "--format=%(refname)", "refs/remotes/"],
                        cwd=checkout, capture=True)
        if not any(ref.startswith("refs/remotes/") for ref in published.splitlines()):
            raise PreparationError(f"Submodule {path} has local unpublished commits; preserving them and refusing to render.")


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
    _check_local_changes(run, directory)
    run(["lfs", "version"])
    progress(f"Updating registered project: git pull --ff-only ({branch} from {upstream})")
    run(["pull", "--ff-only", "--no-rebase", "--recurse-submodules=no"])
    commit = run(["rev-parse", "HEAD"], capture=True)
    remote_commit = run(["rev-parse", "@{upstream}"], capture=True)
    if commit != remote_commit:
        raise PreparationError("Project has local commits beyond its upstream. Resolve them in Anchorpoint before rendering.")
    # Pulling the parent can change its pins. Recheck against the new index
    # before any submodule checkout, including work that arrived during pull.
    _check_local_changes(run, directory)
    progress("Updating project submodules to the versions recorded by the project")
    run(["submodule", "sync", "--recursive"])
    run(["submodule", "update", "--init", "--recursive", "--checkout", "--depth", "1"])
    progress("Downloading current Git LFS assets")
    run(["lfs", "pull", "--include=", "--exclude="])
    run(["submodule", "foreach", "--recursive", "git lfs pull --include= --exclude="])
    if run(["status", "--porcelain", "--untracked-files=no", "--ignore-submodules=untracked"], capture=True):
        raise PreparationError("Project has tracked changes after updating; rendering was not started.")
    commands.check_cancelled()
    if not Path(uproject).is_file():
        raise PreparationError("The registered .uproject was removed by the update. Update its registration before rendering.")
    progress(f"Project update complete: {branch} at {commit[:12]}")
    return commit
