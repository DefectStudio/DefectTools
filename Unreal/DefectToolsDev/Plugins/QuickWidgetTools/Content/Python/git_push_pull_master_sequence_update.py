import importlib
import os
import re
import subprocess

import unreal

import git_push_file as git_tools
import shot_subsequence_version_up as seq_tools

importlib.reload(git_tools)
importlib.reload(seq_tools)


LOG_PREFIX = "[GitPushPullMasterSequenceUpdate]"
ALLOWED_SUBSEQUENCES = set(seq_tools.ALLOWED_SUBSEQUENCES)

# Public state for Blueprint/debug reading after run(...).
master_sequence_file = ""
master_sequence_asset = ""
latest_subsequence_files = []
latest_subsequence_assets = []
changed_files = []
updated_master = False
created_commit = False
pushed = False


class VersionedSubsequenceInfo(object):
    def __init__(self, asset_path, file_path, subsequence_name, version_number, version_digits):
        self.asset_path = asset_path
        self.asset_name = seq_tools._asset_name(asset_path)
        self.file_path = file_path
        self.subsequence_name = subsequence_name
        self.version_number = version_number
        self.version_digits = version_digits


def _reset_outputs():
    global master_sequence_file, master_sequence_asset
    global latest_subsequence_files, latest_subsequence_assets, changed_files
    global updated_master, created_commit, pushed

    master_sequence_file = ""
    master_sequence_asset = ""
    latest_subsequence_files = []
    latest_subsequence_assets = []
    changed_files = []
    updated_master = False
    created_commit = False
    pushed = False


def _log(message):
    unreal.log(f"{LOG_PREFIX} {message}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {message}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {message}")


def _clean_file_path(path):
    return git_tools._clean_file_path(path)


def _run_command(command, cwd=None):
    # Keep local logging under this script prefix instead of GitPushFile's prefix.
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


def _close_open_sequences():
    library = getattr(unreal, "LevelSequenceEditorBlueprintLibrary", None)
    if not library:
        _log_warning("LevelSequenceEditorBlueprintLibrary is unavailable. Could not close open sequences.")
        return False

    for method_name in (
        "close_level_sequence",
        "close_current_level_sequence",
        "close_sequence",
        "close_current_sequence",
    ):
        method = getattr(library, method_name, None)
        if not callable(method):
            continue
        try:
            method()
            _log(f"Closed open sequence using {method_name}().")
            return True
        except TypeError:
            continue
        except Exception as exc:
            _log_warning(f"{method_name} failed: {exc}")

    _log_warning("Could not auto-close Sequencer. Please close open Sequencer tabs before PushPull if this causes save/pull issues.")
    return False


def _scan_asset_paths(asset_paths):
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    directories = []
    for asset_path in asset_paths:
        package_path = seq_tools._asset_package_path(asset_path)
        if package_path.startswith("/Game/"):
            directory = package_path.rsplit("/", 1)[0]
            if directory not in directories:
                directories.append(directory)
    if not directories:
        return
    try:
        registry.scan_paths_synchronous(directories, True)
        _log(f"Scanned asset registry paths: {directories}")
    except Exception as exc:
        _log_warning(f"Asset registry scan failed: {exc}")


def _reload_package_if_possible(asset_path):
    package_path = seq_tools._asset_package_path(asset_path)
    try:
        package = unreal.find_package(None, package_path)
    except Exception:
        package = None
    if not package:
        return False

    utils = getattr(unreal, "EditorLoadingAndSavingUtils", None)
    if not utils:
        return False

    for method_name in ("reload_packages", "reload_packages_with_dialog"):
        method = getattr(utils, method_name, None)
        if not callable(method):
            continue
        try:
            method([package])
            _log(f"Reloaded package from disk: {package_path}")
            return True
        except TypeError:
            continue
        except Exception as exc:
            _log_warning(f"{method_name} failed for {package_path}: {exc}")
    return False


def _version_pattern(shot_name):
    allowed = "|".join(sorted(re.escape(name) for name in ALLOWED_SUBSEQUENCES))
    return re.compile(rf"^{re.escape(shot_name)}_({allowed})_v(\d+)$", re.IGNORECASE)


def _find_all_versioned_subsequences(master_asset_path, shot_name):
    pattern = _version_pattern(shot_name)
    roots = seq_tools._get_subsequence_search_roots(master_asset_path, shot_name)
    found = []

    _log(f"Finding versioned subsequences in roots: {roots}")
    for root in roots:
        try:
            asset_paths = unreal.EditorAssetLibrary.list_assets(root, recursive=True, include_folder=False)
        except Exception as exc:
            _log_warning(f"Could not list assets under {root}: {exc}")
            continue

        for asset_path in asset_paths:
            package_path = seq_tools._asset_package_path(asset_path)
            asset_name = seq_tools._asset_name(package_path)
            match = pattern.fullmatch(asset_name)
            if not match:
                continue
            if not seq_tools._load_level_sequence(package_path):
                continue

            file_path = seq_tools._asset_package_to_file_path(package_path)
            found.append(
                VersionedSubsequenceInfo(
                    package_path,
                    file_path,
                    match.group(1).upper(),
                    int(match.group(2)),
                    max(3, len(match.group(2))),
                )
            )

    found.sort(key=lambda item: (item.subsequence_name, item.version_number, item.version_digits, item.asset_path))
    _log(f"Versioned subsequences found: {len(found)}")
    return found


def _latest_by_subsequence(infos):
    latest = {}
    for info in infos:
        existing = latest.get(info.subsequence_name)
        if not existing:
            latest[info.subsequence_name] = info
            continue
        if (info.version_number, info.version_digits, info.asset_path) > (existing.version_number, existing.version_digits, existing.asset_path):
            latest[info.subsequence_name] = info
    return latest


def _is_loaded_asset_dirty(asset):
    if not asset:
        return False

    for method_name in ("is_dirty", "is_asset_dirty"):
        method = getattr(asset, method_name, None)
        if callable(method):
            try:
                return bool(method())
            except Exception:
                pass

    package = None
    for method_name in ("get_outermost", "get_package"):
        method = getattr(asset, method_name, None)
        if callable(method):
            try:
                package = method()
                if package:
                    break
            except Exception:
                pass

    if package:
        for method_name in ("is_dirty", "is_package_dirty"):
            method = getattr(package, method_name, None)
            if callable(method):
                try:
                    return bool(method())
                except Exception:
                    pass

    return False


def _save_master_if_dirty(master_sequence, master_asset_path, label):
    if not _is_loaded_asset_dirty(master_sequence):
        _log(f"Master sequence is clean during {label}; skipping master save.")
        return True

    _log(f"Master sequence is dirty during {label}; saving local master.")
    return seq_tools._save_loaded_asset(master_sequence, master_asset_path)


def _save_asset_list(master_sequence, master_asset_path, subsequence_infos):
    save_ok = True

    if not _save_master_if_dirty(master_sequence, master_asset_path, "pre-pull save"):
        save_ok = False

    for info in subsequence_infos:
        asset = seq_tools._load_level_sequence(info.asset_path)
        if asset and not seq_tools._save_loaded_asset(asset, info.asset_path):
            save_ok = False
    return save_ok


def _repo_rel(repo_root, file_path):
    return git_tools._to_repo_relative(repo_root, file_path)


def _repo_abs(repo_root, rel_path):
    if not rel_path:
        return ""
    return _clean_file_path(os.path.join(repo_root, rel_path))


def _build_git_scope(repo_root, master_file):
    master_rel = _repo_rel(repo_root, master_file)
    shot_folder_rel = _repo_rel(repo_root, os.path.splitext(master_file)[0])
    scope = [master_rel]
    if os.path.exists(os.path.join(repo_root, shot_folder_rel)):
        scope.append(shot_folder_rel)
    return git_tools._dedupe(scope), master_rel


def _parse_status_paths(status_text):
    paths = set()
    for line in status_text.splitlines():
        if not line.strip():
            continue
        path_text = line[3:].strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1].strip()
        if path_text:
            paths.add(_clean_file_path(path_text))
    return paths


def _git_status_paths(repo_root, rel_paths):
    code, stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "status", "--porcelain", "--"] + list(rel_paths))
    if code != 0:
        return None
    return _parse_status_paths(stdout_text)


def _git_diff_paths(repo_root, left_right, rel_paths):
    code, stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "diff", "--name-only", left_right, "--"] + list(rel_paths))
    if code != 0:
        return None
    return set(_clean_file_path(line) for line in stdout_text.splitlines() if line.strip())


def _current_branch(repo_root):
    code, stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"])
    return stdout_text.strip() if code == 0 else ""


def _upstream_ref(repo_root):
    code, stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if code == 0 and stdout_text.strip():
        return stdout_text.strip()
    branch = _current_branch(repo_root)
    if branch:
        fallback = f"origin/{branch}"
        _log_warning(f"No upstream was configured. Falling back to {fallback}.")
        return fallback
    return ""


def _git_lfs_prepare(repo_root):
    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "lfs", "version"])
    if code != 0:
        _log_error("Git LFS is not available to Unreal. Install Git LFS and make sure git-lfs is on PATH.")
        return False
    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "lfs", "install", "--local"])
    if code != 0:
        _log_error("git lfs install --local failed.")
        return False
    return True


def _restore_paths(repo_root, rel_paths):
    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "checkout", "--"] + list(rel_paths))
    if code != 0:
        _log_error(f"Could not restore paths before pull: {rel_paths}")
        return False
    return True


def _section_family(section, shot_name):
    current_sequence = seq_tools._get_section_sequence(section)
    current_path = seq_tools._get_sequence_asset_path(current_sequence)
    current_name = seq_tools._asset_name(current_path)
    match = _version_pattern(shot_name).fullmatch(current_name)
    if not match:
        return "", current_path
    return match.group(1).upper(), current_path


def _update_master_to_latest(master_sequence, shot_name, latest_map):
    global updated_master
    changed_count = 0

    for section in seq_tools._get_subsequence_sections(master_sequence):
        family, current_path = _section_family(section, shot_name)
        if not family or family not in latest_map:
            continue

        latest_info = latest_map[family]
        if current_path == latest_info.asset_path:
            _log(f"Master already points {family} at latest: {latest_info.asset_name}")
            continue

        latest_asset = seq_tools._load_level_sequence(latest_info.asset_path)
        if not latest_asset:
            _log_warning(f"Could not load latest {family}: {latest_info.asset_path}")
            continue

        if seq_tools._set_section_sequence(section, latest_asset):
            changed_count += 1
            _log(f"Updated master {family}: {seq_tools._asset_name(current_path)} -> {latest_info.asset_name}")

    if changed_count:
        seq_tools._mark_dirty(master_sequence)
        updated_master = True

    _log(f"Master latest-version updates applied: {changed_count}")
    return changed_count


def _commit_message_for_paths(shot_name, rel_paths):
    pattern = _version_pattern(shot_name)
    families = []

    for rel_path in rel_paths:
        asset_name = os.path.splitext(os.path.basename(rel_path))[0]
        match = pattern.fullmatch(asset_name)
        if not match:
            continue

        family = match.group(1).upper()
        if family not in families:
            families.append(family)

    if not families:
        return f"PushPull {shot_name}"

    family_text = ",".join(sorted(families))
    return f"PushPull {shot_name} {family_text}"


def _commit_and_push(repo_root, rel_paths_to_commit, shot_name):
    global created_commit, pushed

    rel_paths = git_tools._dedupe([_clean_file_path(path) for path in rel_paths_to_commit if path])
    if not rel_paths:
        _log("No changed or untracked shot files found. Nothing to commit or push.")
        return True

    _log("Changed/untracked shot files selected for git add:")
    for rel_path in rel_paths:
        _log(f"  {rel_path}")

    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "add", "--"] + rel_paths)
    if code != 0:
        _log_error("git add failed.")
        return False

    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "diff", "--cached", "--quiet"])
    if code == 1:
        message = _commit_message_for_paths(shot_name, rel_paths)
        _log(f"Commit message: {message}")
        code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "commit", "-m", message])
        if code != 0:
            _log_error("git commit failed.")
            return False
        created_commit = True
    elif code == 0:
        _log("No staged changes found after git add. Nothing to commit or push.")
        return True
    else:
        _log_error("git diff --cached failed.")
        return False

    # Normal git push triggers Git LFS's pre-push hook when LFS is installed.
    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "push"])
    if code != 0:
        _log_error("git push failed. Someone may have pushed between your pull and push. Run PushPull again.")
        return False
    pushed = True
    return True


def run(shot_name):
    """
    Pull latest shot subsequences, update the shot master sequence so each
    subsequence section points at the latest v### asset, then commit and push only
    the shot files that Git reports as changed or untracked.
    """
    global master_sequence_file, master_sequence_asset
    global latest_subsequence_files, latest_subsequence_assets, changed_files

    _reset_outputs()
    _log("----- run() called -----")
    _log(f"Raw shot_name: {shot_name!r}")

    sanitized_shot = seq_tools._sanitize_shot_name(shot_name)
    if not sanitized_shot:
        _log_error("shot_name is empty after sanitizing.")
        return False

    _close_open_sequences()

    master_sequence, master_asset_path = seq_tools._find_master_sequence(sanitized_shot)
    if not master_sequence:
        _log_error(f"Could not find master Level Sequence for shot: {sanitized_shot}")
        return False

    master_sequence_asset = master_asset_path
    master_sequence_file = seq_tools._asset_package_to_file_path(master_asset_path)
    if not master_sequence_file or not os.path.exists(master_sequence_file):
        _log_error(f"Could not resolve master sequence file: {master_asset_path}")
        return False

    local_subsequences = _find_all_versioned_subsequences(master_asset_path, sanitized_shot)
    if not local_subsequences:
        _log_error(f"No local versioned subsequences found for shot: {sanitized_shot}")
        return False

    _save_asset_list(master_sequence, master_asset_path, local_subsequences)

    repo_root = git_tools._find_git_root(master_sequence_file)
    if not repo_root:
        _log_error(f"Could not find Git repo root for: {master_sequence_file}")
        return False
    _log(f"Git repo root: {repo_root}")

    if not _git_lfs_prepare(repo_root):
        return False

    scope_paths, master_rel = _build_git_scope(repo_root, master_sequence_file)
    _log(f"Shot Git scope: {scope_paths}")

    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "fetch", "--all", "--prune"])
    if code != 0:
        _log_error("git fetch failed.")
        return False

    upstream = _upstream_ref(repo_root)
    if not upstream:
        _log_error("Could not determine upstream branch.")
        return False
    _log(f"Upstream ref: {upstream}")

    local_changed = _git_status_paths(repo_root, scope_paths)
    remote_changed = _git_diff_paths(repo_root, f"HEAD..{upstream}", scope_paths)
    if local_changed is None or remote_changed is None:
        return False

    _log(f"Local changed shot paths before pull: {sorted(local_changed)}")
    _log(f"Remote changed shot paths before pull: {sorted(remote_changed)}")

    overlap = set(local_changed).intersection(remote_changed)
    unsafe_overlap = sorted(path for path in overlap if path != master_rel)
    if unsafe_overlap:
        _log_error("Same-file local/remote collision detected on binary Unreal assets.")
        for path in unsafe_overlap:
            _log_error(f"Collision path: {path}")
        _log_error("Pull manually, resolve the version naming collision, then run PushPull again.")
        return False

    if master_rel in overlap:
        _log_warning("Local and remote both changed the master. Restoring local master before pull; it will be rebuilt after pull.")
        if not _restore_paths(repo_root, [master_rel]):
            return False

    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "pull", "--ff-only"])
    if code != 0:
        _log_error("git pull --ff-only failed. Resolve Git manually, then run PushPull again.")
        return False

    code, _stdout_text, _stderr_text = _run_command(["git", "-C", repo_root, "lfs", "pull"])
    if code != 0:
        _log_error("git lfs pull failed.")
        return False

    _scan_asset_paths([master_asset_path])
    _reload_package_if_possible(master_asset_path)

    master_sequence = seq_tools._load_level_sequence(master_asset_path)
    if not master_sequence:
        _log_error(f"Could not reload master sequence after pull: {master_asset_path}")
        return False

    all_subsequences = _find_all_versioned_subsequences(master_asset_path, sanitized_shot)
    latest_map = _latest_by_subsequence(all_subsequences)
    if not latest_map:
        _log_error("Could not determine latest subsequence versions after pull.")
        return False

    _log("Latest subsequence versions after pull:")
    for key in sorted(latest_map):
        _log(f"  {key}: {latest_map[key].asset_name}")

    latest_infos = [latest_map[key] for key in sorted(latest_map)]
    latest_subsequence_assets = [info.asset_path for info in latest_infos]
    latest_subsequence_files = [info.file_path for info in latest_infos if info.file_path]

    updates_applied = _update_master_to_latest(master_sequence, sanitized_shot, latest_map)
    if updates_applied:
        if not seq_tools._save_loaded_asset(master_sequence, master_asset_path):
            return False
        seq_tools._refresh_sequencer_if_possible()
    else:
        _log("Master was already latest after pull; skipping post-update master save.")

    final_changed_rel_paths = _git_status_paths(repo_root, scope_paths)
    if final_changed_rel_paths is None:
        return False

    changed_files = [_repo_abs(repo_root, rel_path) for rel_path in sorted(final_changed_rel_paths)]
    _log(f"Changed/untracked shot paths after pull/master update: {sorted(final_changed_rel_paths)}")

    if not _commit_and_push(repo_root, sorted(final_changed_rel_paths), sanitized_shot):
        return False

    _log("PushPull master sequence update complete.")
    _log(f"Master sequence file: {master_sequence_file}")
    _log(f"Latest subsequence files: {latest_subsequence_files}")
    _log(f"Changed files committed: {changed_files}")
    return True


if __name__ == "__main__":
    run("")
