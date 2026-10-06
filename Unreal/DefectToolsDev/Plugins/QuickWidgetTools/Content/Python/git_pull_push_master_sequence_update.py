import importlib

import unreal

import git_push_pull_master_sequence_update as _impl


LOG_PREFIX = "[GitPullPushMasterSequenceUpdate]"

# Public state for Blueprint/debug reading after run(...).
master_sequence_file = ""
master_sequence_asset = ""
latest_subsequence_files = []
latest_subsequence_assets = []
changed_files = []
updated_master = False
created_commit = False
pushed = False


def _rename_pushpull_text(message):
    return str(message).replace("PushPull", "PullPush")


def _log(message):
    unreal.log(f"{LOG_PREFIX} {_rename_pushpull_text(message)}")


def _log_warning(message):
    unreal.log_warning(f"{LOG_PREFIX} Warning: {_rename_pushpull_text(message)}")


def _log_error(message):
    unreal.log_error(f"{LOG_PREFIX} Error: {_rename_pushpull_text(message)}")


def _sync_public_state():
    global master_sequence_file, master_sequence_asset
    global latest_subsequence_files, latest_subsequence_assets, changed_files
    global updated_master, created_commit, pushed

    master_sequence_file = getattr(_impl, "master_sequence_file", "")
    master_sequence_asset = getattr(_impl, "master_sequence_asset", "")
    latest_subsequence_files = list(getattr(_impl, "latest_subsequence_files", []))
    latest_subsequence_assets = list(getattr(_impl, "latest_subsequence_assets", []))
    changed_files = list(getattr(_impl, "changed_files", []))
    updated_master = bool(getattr(_impl, "updated_master", False))
    created_commit = bool(getattr(_impl, "created_commit", False))
    pushed = bool(getattr(_impl, "pushed", False))


def _patch_impl():
    _impl.LOG_PREFIX = LOG_PREFIX
    _impl._log = _log
    _impl._log_warning = _log_warning
    _impl._log_error = _log_error

    original_commit_message_for_paths = _impl._commit_message_for_paths

    def _commit_message_for_paths(shot_name, rel_paths):
        return _rename_pushpull_text(original_commit_message_for_paths(shot_name, rel_paths))

    _impl._commit_message_for_paths = _commit_message_for_paths


def run(shot_name):
    """
    Pull latest shot subsequences, update the shot master sequence so each
    subsequence section points at the latest v### asset, then commit and push only
    the shot files that Git reports as changed or untracked.
    """
    global _impl

    _impl = importlib.reload(_impl)
    _patch_impl()

    result = _impl.run(shot_name)
    _sync_public_state()
    return result


_patch_impl()
_sync_public_state()


if __name__ == "__main__":
    run("")
