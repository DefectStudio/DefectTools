"""Update an explicitly registered checkout before rendering; never discover or clone it."""

from pathlib import Path, PurePosixPath
import re
import shutil
import time

from portable_pipe_tools.app_runtime import prepare_external_programs
from portable_pipe_tools.render_farm.project_workspace import ProjectWorkspace, PreparationError, PreparationCancelled

SYNC_POLICY = "latest_branch_git_pull_ff_only"
OVERRIDE_SYNC_POLICY = "latest_branch_override_local_changes"


def _contained_checkout(directory: Path, path: Path) -> Path:
    root = directory.resolve()
    resolved = path.resolve()
    if root == Path(root.anchor) or not root.is_dir() or not resolved.is_relative_to(root):
        raise PreparationError("Checkout resolves outside the registered project; rendering was not started.")
    return resolved


def _submodule_checkouts(run, directory):
    metadata = run(["submodule", "foreach", "--quiet", "--recursive",
                    'current=$(git rev-parse HEAD) || exit; '
                    'printf "module\\000%s\\000%s\\000%s\\000" "$displaypath" "$sha1" "$current"'], capture=True)
    fields = metadata.split("\0")[:-1] if metadata else []
    if len(fields) % 4 or any(fields[index] != "module" for index in range(0, len(fields), 4)):
        raise PreparationError("Could not safely inspect project submodules; rendering was not started.")
    checkouts = []
    for index in range(0, len(fields), 4):
        checkout = _contained_checkout(directory, directory / fields[index + 1])
        actual_root = Path(run(["rev-parse", "--show-toplevel"], cwd=checkout, capture=True)).resolve()
        if actual_root != checkout:
            raise PreparationError("Submodule Git worktree is redirected outside its project path; rendering was not started.")
        checkouts.append((checkout, fields[index + 2], fields[index + 3]))
    return checkouts


def _validate_reset_paths(run, directory, commit):
    for args in (["ls-tree", "-r", "--name-only", "-z", commit],
                 ["ls-files", "-z"],
                 ["ls-files", "--others", "--exclude-standard", "--directory", "-z"]):
        paths = run(args, cwd=directory, capture=True)
        for name in paths.split("\0"):
            if name:
                _contained_checkout(directory, directory / name)


def _override_update(run, directory, uproject, branch, progress):
    remote = run(["config", "--get", f"branch.{branch}.remote"], capture=True)
    merge_ref = run(["config", "--get-all", f"branch.{branch}.merge"], capture=True)
    upstream_ref = run(["rev-parse", "--symbolic-full-name", "@{upstream}"], capture=True)
    if (not remote or remote == "." or "\n" in remote or remote.startswith("-")
            or "\n" in merge_ref or not merge_ref.startswith("refs/heads/")
            or not upstream_ref.startswith("refs/remotes/") or "\n" in upstream_ref):
        raise PreparationError("Override Local Changes requires one configured remote branch upstream.")
    progress(f"Override Local Changes enabled: fetching latest {branch} from {remote} before discarding local differences")
    run(["fetch", "--no-tags", "--recurse-submodules=no", remote,
         f"+{merge_ref}:{upstream_ref}"])
    commit = run(["rev-parse", "--verify", upstream_ref + "^{commit}"], capture=True)
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise PreparationError("Could not verify the fetched upstream commit; local files were not overridden.")
    relative_project = uproject.resolve().relative_to(directory.resolve()).as_posix()
    if run(["cat-file", "-t", f"{commit}:{relative_project}"], capture=True) != "blob":
        raise PreparationError("The latest remote version does not contain the registered .uproject; local files were not overridden.")
    # Inspect every initialized child before the first destructive operation.
    # Reject redirected/junction checkouts rather than touching another folder.
    children = _submodule_checkouts(run, directory)
    _validate_reset_paths(run, directory, commit)
    for checkout, _, _ in children:
        _validate_reset_paths(run, checkout, "HEAD")
    if run(["branch", "--show-current"], capture=True) != branch:
        raise PreparationError("Project branch changed during preparation; local files were not overridden.")
    _contained_checkout(directory, directory)
    progress(f"Discarding local tracked changes and untracked files in {directory}; no backup. Routine cleaning excludes ignored files.")
    for checkout, _, _ in reversed(children):
        run(["reset", "--hard", "--no-recurse-submodules", "HEAD"], cwd=checkout)
        run(["clean", "-fd"], cwd=checkout)
    run(["reset", "--hard", "--no-recurse-submodules", commit])
    run(["clean", "-fd"])
    return commit, children


def _remove_obsolete_submodules(run, directory, old_children, update, progress, cancelled):
    current = [checkout for checkout, _, _ in _submodule_checkouts(run, directory)]
    removed = []
    for checkout, _, _ in sorted(old_children, key=lambda child: len(child[0].parts)):
        if checkout in current or any(checkout.is_relative_to(parent) for parent in removed):
            continue
        if _contained_checkout(directory, checkout) != checkout:
            raise PreparationError("Obsolete plugin path was redirected during preparation; rendering was not started.")
        if not checkout.is_dir():
            continue  # A committed replacement file is already in place.
        # The only recursively removed directories are known former submodule
        # worktrees. Keep their object storage in the containing .git/modules.
        if (checkout / ".git").exists():
            actual_root = Path(run(["rev-parse", "--show-toplevel"], cwd=checkout, capture=True)).resolve()
            if actual_root != checkout:
                raise PreparationError("Obsolete plugin Git worktree was redirected; rendering was not started.")
        parent = max((path for path in [directory, *current]
                      if checkout != path and checkout.is_relative_to(path)), key=lambda path: len(path.parts))
        relative = checkout.relative_to(parent).as_posix()
        replacement = run(["ls-tree", "HEAD", "--", relative], cwd=parent, capture=True)
        if replacement.startswith("160000 "):
            raise PreparationError("A required plugin was not initialized; rendering was not started.")
        if cancelled():
            raise PreparationCancelled("Preparation cancelled before removing an obsolete plugin")
        progress(f"Removing obsolete managed plugin worktree {checkout}; its local files and caches are discarded without a backup.")
        try:
            shutil.rmtree(checkout)
        except OSError as error:
            raise PreparationError(f"Could not remove obsolete plugin worktree {checkout}: {error}") from error
        removed.append(checkout)
        if replacement:
            run(["restore", "--source=HEAD", "--worktree", "--", relative], cwd=parent)
    if removed:
        # A replacement ordinary directory can itself contain newly pinned
        # submodules, so restore their worktrees after this scoped cleanup.
        run(update)


def _verify_override_update(run, directory, branch, commit, progress):
    if (run(["branch", "--show-current"], capture=True) != branch
            or run(["rev-parse", "HEAD"], capture=True) != commit):
        raise PreparationError("Project branch or commit changed during override preparation; rendering was not started.")
    # Compare actual filtered contents, not just stat metadata. LFS hydration
    # can leave status reporting M for an unchanged pointer-backed asset.
    options = ["--exit-code", "--no-ext-diff", "--no-textconv"]
    run(["diff", "--cached", *options, "--ignore-submodules=none", commit, "--"])
    run(["diff", *options, "--ignore-submodules=all", commit, "--"])
    for checkout, pinned, current in _submodule_checkouts(run, directory):
        if current != pinned:
            raise PreparationError(f"Submodule {checkout.relative_to(directory.resolve())} does not match its project pin.")
        run(["diff", "--cached", *options, "--ignore-submodules=none", "HEAD", "--"], cwd=checkout)
        run(["diff", *options, "--ignore-submodules=all", "HEAD", "--"], cwd=checkout)
    for checkout in [directory, *(child[0] for child in _submodule_checkouts(run, directory))]:
        remaining = run(["ls-files", "--others", "--exclude-standard", "--directory", "--no-empty-directory", "-z"],
                        cwd=checkout, capture=True)
        if remaining:
            raise PreparationError("Untracked local files or an embedded Git repository survived cleanup; "
                                   "rendering was not started. Remove it from the registered checkout: "
                                   + " | ".join(remaining.rstrip("\0").split("\0")[:5]))
    status = run(["status", "--porcelain", "--untracked-files=no", "--ignore-submodules=untracked"], capture=True)
    if status:
        progress("Git reports modified-file metadata, but tracked contents and plugin pins match the fetched version; override verification passed.")


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
                            cancelled=lambda: False, timeout_seconds=1800,
                            override_local_changes=False) -> str:
    """Caller holds the project lock through sync, runtime installation and render."""
    if type(override_local_changes) is not bool:
        raise ValueError("Override Local Changes must be enabled explicitly with a boolean.")
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
    if override_local_changes:
        run(["lfs", "version"])
        directory = _contained_checkout(directory, directory)
        commit, old_children = _override_update(run, directory, Path(uproject), branch, progress)
    else:
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
    if override_local_changes:
        _submodule_checkouts(run, directory)
    update = ["submodule", "update", "--init", "--recursive", "--checkout", "--depth", "1"]
    if override_local_changes:
        update.append("--force")
    run(update)
    if override_local_changes:
        _remove_obsolete_submodules(run, directory, old_children, update, progress, cancelled)
    progress("Downloading current Git LFS assets")
    run(["lfs", "pull", "--include=", "--exclude="])
    run(["submodule", "foreach", "--recursive", "git lfs pull --include= --exclude="])
    if override_local_changes:
        _verify_override_update(run, directory, branch, commit, progress)
    elif run(["status", "--porcelain", "--untracked-files=no", "--ignore-submodules=untracked"], capture=True):
        raise PreparationError("Project has tracked changes after updating; rendering was not started.")
    commands.check_cancelled()
    if not Path(uproject).is_file():
        raise PreparationError("The registered .uproject was removed by the update. Update its registration before rendering.")
    progress(f"Project update complete: {branch} at {commit[:12]}")
    return commit
