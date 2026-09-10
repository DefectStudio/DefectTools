from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import subprocess

from portable_pipe_tools.render_farm.queue import retry_transient_windows_lock


LOGGER = logging.getLogger("render_worker")

GIT_PULL_LOG_FILENAME = "git_pull.log"
DEFAULT_GIT_PULL_TIMEOUT_SECONDS = 30.0 * 60.0

_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40,64}")
GitCommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class GitPullError(RuntimeError):
    """Raised when a worker checkout cannot be safely updated."""


@dataclass(frozen=True)
class GitPullResult:
    repository_root: Path
    branch: str
    upstream: str
    commit_before: str
    commit_after: str
    summary: str
    transcript: str


def _run_git_command(
    repository_directory: Path,
    arguments: list[str],
    *,
    timeout_seconds: float,
    command_runner: GitCommandRunner,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repository_directory), *arguments]
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return command_runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=environment,
            creationflags=creation_flags,
        )
    except FileNotFoundError as error:
        raise GitPullError(
            "Git is not installed or is not available on this worker's PATH."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise GitPullError(
            f"Git command exceeded its {timeout_seconds:.0f}-second timeout: "
            f"git {' '.join(arguments)}"
        ) from error
    except OSError as error:
        raise GitPullError(f"Could not run Git: {error}") from error


def _command_text(arguments: list[str]) -> str:
    return f"$ git {' '.join(arguments)}"


def _append_transcript(
    transcript_lines: list[str],
    arguments: list[str],
    completed: subprocess.CompletedProcess[str],
) -> None:
    transcript_lines.append(_command_text(arguments))
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if stdout:
        transcript_lines.append(stdout)
    if stderr:
        transcript_lines.append(stderr)
    transcript_lines.append(f"[exit code {completed.returncode}]")


def _require_success(
    arguments: list[str],
    completed: subprocess.CompletedProcess[str],
    description: str,
) -> str:
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "No Git details"
        raise GitPullError(f"{description}: {detail}")
    return completed.stdout.strip()


def _require_commit(value: str, description: str) -> str:
    commit = value.strip()
    if not _COMMIT_RE.fullmatch(commit):
        raise GitPullError(f"{description}: Git returned {commit!r}")
    return commit.lower()


def _run_and_record(
    repository_directory: Path,
    arguments: list[str],
    transcript_lines: list[str],
    *,
    timeout_seconds: float,
    command_runner: GitCommandRunner,
) -> subprocess.CompletedProcess[str]:
    completed = _run_git_command(
        repository_directory,
        arguments,
        timeout_seconds=timeout_seconds,
        command_runner=command_runner,
    )
    _append_transcript(transcript_lines, arguments, completed)
    return completed


def pull_latest_branch(
    project_directory: str | Path,
    *,
    timeout_seconds: float = DEFAULT_GIT_PULL_TIMEOUT_SECONDS,
    command_runner: GitCommandRunner | None = None,
) -> GitPullResult:
    """Fast-forward a clean worker checkout to its latest upstream branch."""
    if timeout_seconds <= 0:
        raise ValueError("Git pull timeout must be greater than zero.")

    selected_directory = Path(
        os.path.abspath(Path(project_directory).expanduser())
    )
    if not selected_directory.is_dir():
        raise GitPullError(
            f"The worker project directory does not exist: {selected_directory}"
        )

    runner = command_runner or subprocess.run
    transcript_lines: list[str] = []

    root_args = ["rev-parse", "--show-toplevel"]
    root_result = _run_and_record(
        selected_directory,
        root_args,
        transcript_lines,
        timeout_seconds=30.0,
        command_runner=runner,
    )
    root_text = _require_success(
        root_args,
        root_result,
        "The selected Unreal project is not inside a Git checkout",
    )
    repository_root = Path(root_text)

    branch_args = ["branch", "--show-current"]
    branch_result = _run_and_record(
        repository_root,
        branch_args,
        transcript_lines,
        timeout_seconds=30.0,
        command_runner=runner,
    )
    branch = _require_success(
        branch_args,
        branch_result,
        "Could not determine the worker Git branch",
    )
    if not branch:
        raise GitPullError(
            "The worker checkout is in detached-HEAD mode. Check out the render "
            "branch before starting the worker."
        )

    status_args = ["status", "--porcelain", "--untracked-files=all"]
    status_result = _run_and_record(
        repository_root,
        status_args,
        transcript_lines,
        timeout_seconds=60.0,
        command_runner=runner,
    )
    status = _require_success(
        status_args,
        status_result,
        "Could not inspect the worker Git checkout",
    )
    if status:
        preview = " | ".join(status.splitlines()[:5])
        raise GitPullError(
            "The worker Git checkout has local or untracked changes. Commit, "
            f"discard, move, or ignore them before rendering. First changes: {preview}"
        )

    before_args = ["rev-parse", "HEAD"]
    before_result = _run_and_record(
        repository_root,
        before_args,
        transcript_lines,
        timeout_seconds=30.0,
        command_runner=runner,
    )
    commit_before = _require_commit(
        _require_success(
            before_args,
            before_result,
            "Could not determine the worker's current Git commit",
        ),
        "Could not determine the worker's current Git commit",
    )

    upstream_args = [
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
    ]
    upstream_result = _run_and_record(
        repository_root,
        upstream_args,
        transcript_lines,
        timeout_seconds=30.0,
        command_runner=runner,
    )
    upstream = _require_success(
        upstream_args,
        upstream_result,
        f"Git branch '{branch}' has no configured upstream branch",
    )

    pull_args = ["pull", "--ff-only"]
    LOGGER.info("Pulling latest Git branch '%s' from '%s'.", branch, upstream)
    pull_result = _run_and_record(
        repository_root,
        pull_args,
        transcript_lines,
        timeout_seconds=timeout_seconds,
        command_runner=runner,
    )
    pull_output = _require_success(
        pull_args,
        pull_result,
        f"Git pull --ff-only failed for branch '{branch}'",
    )

    final_status_result = _run_and_record(
        repository_root,
        status_args,
        transcript_lines,
        timeout_seconds=60.0,
        command_runner=runner,
    )
    final_status = _require_success(
        status_args,
        final_status_result,
        "Could not verify the worker checkout after Git pull",
    )
    if final_status:
        preview = " | ".join(final_status.splitlines()[:5])
        raise GitPullError(
            "The worker checkout was not clean after Git pull. First changes: "
            f"{preview}"
        )

    after_args = ["rev-parse", "HEAD"]
    after_result = _run_and_record(
        repository_root,
        after_args,
        transcript_lines,
        timeout_seconds=30.0,
        command_runner=runner,
    )
    commit_after = _require_commit(
        _require_success(
            after_args,
            after_result,
            "Could not determine the pulled Git commit",
        ),
        "Could not determine the pulled Git commit",
    )

    divergence_args = [
        "rev-list",
        "--left-right",
        "--count",
        f"HEAD...{upstream}",
    ]
    divergence_result = _run_and_record(
        repository_root,
        divergence_args,
        transcript_lines,
        timeout_seconds=60.0,
        command_runner=runner,
    )
    divergence = _require_success(
        divergence_args,
        divergence_result,
        "Could not compare the pulled branch with its upstream",
    )
    try:
        ahead_text, behind_text = divergence.split()
        ahead = int(ahead_text)
        behind = int(behind_text)
    except (TypeError, ValueError) as error:
        raise GitPullError(
            f"Git returned an invalid branch-divergence result: {divergence!r}"
        ) from error
    if ahead or behind:
        raise GitPullError(
            f"Worker branch '{branch}' does not exactly match '{upstream}' after "
            f"pull (ahead={ahead}, behind={behind})."
        )

    summary = pull_output.splitlines()[-1] if pull_output else "Git pull completed."
    LOGGER.info(
        "Git checkout ready: branch=%s, upstream=%s, commit=%s",
        branch,
        upstream,
        commit_after,
    )
    return GitPullResult(
        repository_root=repository_root,
        branch=branch,
        upstream=upstream,
        commit_before=commit_before,
        commit_after=commit_after,
        summary=summary,
        transcript="\n".join(transcript_lines).rstrip() + "\n",
    )


def write_git_pull_log(path: Path, result: GitPullResult) -> None:
    retry_transient_windows_lock(
        lambda: path.write_text(
            result.transcript,
            encoding="utf-8",
            newline="\n",
        ),
        description=f"Write Git pull log {path}",
    )
