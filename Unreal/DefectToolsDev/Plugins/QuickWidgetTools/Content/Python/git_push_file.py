import os
import subprocess
import unreal


LOG_PREFIX = "[GitPushFile]"


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _clean_file_path(path):
    text = str(path or "").strip().strip('"').replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    return text


def _project_content_dir():
    try:
        path = unreal.Paths.project_content_dir()
        if path:
            return _clean_file_path(unreal.Paths.convert_relative_path_to_full(path))
    except Exception:
        pass

    try:
        path = unreal.SystemLibrary.get_project_content_directory()
        if path:
            return _clean_file_path(path)
    except Exception:
        pass

    return ""


def _asset_package_path(asset_path):
    text = str(asset_path or "").strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    if "." in text:
        text = text.split(".", 1)[0]
    if len(text) > 1:
        text = text.rstrip("/")
    return text


def _asset_package_to_file_path(asset_path):
    package_path = _asset_package_path(asset_path)
    if not package_path.startswith("/Game/"):
        return ""

    content_dir = _project_content_dir()
    if not content_dir:
        return ""

    relative_path = package_path[len("/Game/"):] + ".uasset"
    return _clean_file_path(os.path.join(content_dir, relative_path))


def _normalize_input_file(path):
    cleaned = _clean_file_path(path)
    if cleaned.startswith("/Game/"):
        return _asset_package_to_file_path(cleaned)
    return cleaned


def _dedupe(paths):
    result = []
    seen = set()

    for path in paths:
        cleaned = _normalize_input_file(path)
        if not cleaned:
            continue

        key = cleaned.lower()
        if key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

    return result


def _existing_companion_files(file_path):
    """
    Unreal assets are usually just .uasset, but some assets can produce sidecar files.
    Include any sidecars that exist so Git does not miss binary companions.
    """
    cleaned = _clean_file_path(file_path)
    base, ext = os.path.splitext(cleaned)

    candidates = [cleaned]
    if ext.lower() == ".uasset":
        candidates.extend([
            base + ".uexp",
            base + ".ubulk",
            base + ".uptnl",
        ])

    return [path for path in candidates if os.path.exists(path)]


def _run_command(command, cwd=None):
    _log(f"Running command: {' '.join(command)}")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout_text, stderr_text = process.communicate()

    if stdout_text:
        _log(stdout_text.strip())
    if stderr_text:
        _log_warning(stderr_text.strip())

    return process.returncode, stdout_text, stderr_text


def _find_git_root(start_file):
    start_file = _clean_file_path(start_file)
    start_dir = start_file if os.path.isdir(start_file) else os.path.dirname(start_file)

    if not start_dir or not os.path.exists(start_dir):
        return ""

    code, stdout_text, _stderr_text = _run_command(
        ["git", "-C", start_dir, "rev-parse", "--show-toplevel"]
    )
    if code != 0:
        return ""

    return _clean_file_path(stdout_text.strip())


def _to_repo_relative(repo_root, file_path):
    rel_path = os.path.relpath(file_path, repo_root)
    return _clean_file_path(rel_path)


def _build_commit_message(primary_file):
    file_name = os.path.basename(primary_file)
    return f"Version up subsequence {file_name}"


def run(new_subsequence_file, extra_files=None, commit_message=None, push=True):
    """
    Add, commit, and push a newly created Unreal asset file.

    Args:
        new_subsequence_file (str): Absolute .uasset path, or a /Game/... asset path.
        extra_files (list[str], optional): Additional files to include, such as the changed master sequence.
        commit_message (str, optional): Custom Git commit message.
        push (bool): If True, run git push after committing.

    Returns:
        bool: True on success, False on failure.
    """
    _log("----- run() called -----")
    _log(f"Raw new_subsequence_file: {new_subsequence_file!r}")

    primary_file = _normalize_input_file(new_subsequence_file)
    if not primary_file:
        _log_error("new_subsequence_file is empty or could not be resolved.")
        return False

    if not os.path.exists(primary_file):
        _log_error(f"File does not exist on disk: {primary_file}")
        return False

    input_files = [primary_file]
    if extra_files:
        if isinstance(extra_files, (list, tuple, set)):
            input_files.extend(list(extra_files))
        else:
            input_files.append(extra_files)

    files_to_commit = []
    for file_path in _dedupe(input_files):
        files_to_commit.extend(_existing_companion_files(file_path))

    files_to_commit = _dedupe(files_to_commit)
    if not files_to_commit:
        _log_error("No existing files were found to commit.")
        return False

    repo_root = _find_git_root(primary_file)
    if not repo_root:
        _log_error(f"Could not find Git repository root for: {primary_file}")
        return False

    _log(f"Git repository root: {repo_root}")

    rel_paths = [_to_repo_relative(repo_root, file_path) for file_path in files_to_commit]

    _log("Files selected for git add/commit:")
    for rel_path in rel_paths:
        _log(f"  {rel_path}")

    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "add", "--"] + rel_paths)
    if code != 0:
        _log_error("git add failed.")
        return False

    code, _stdout_text, _stderr_text = _run_command(
        ["git", "-C", repo_root, "diff", "--cached", "--quiet", "--"] + rel_paths
    )
    if code == 0:
        _log_warning("No staged changes found after git add. Nothing to commit.")
        return False
    if code not in (0, 1):
        _log_error("git diff --cached failed.")
        return False

    final_commit_message = commit_message or _build_commit_message(primary_file)
    code, _stdout_text, _stderr_text = _run_command(
        ["git", "-C", repo_root, "commit", "-m", final_commit_message, "--"] + rel_paths
    )
    if code != 0:
        _log_error("git commit failed.")
        return False

    if push:
        code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "push"])
        if code != 0:
            _log_error("git push failed.")
            return False

    _log("Git push file complete.")
    return True


if __name__ == "__main__":
    run("")
