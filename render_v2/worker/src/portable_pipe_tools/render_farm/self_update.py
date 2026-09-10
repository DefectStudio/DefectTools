from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
from pathlib import Path

from portable_pipe_tools.render_farm.git_sync import (
    GitPullResult,
    pull_latest_branch,
)


RENDER_WORKER_RESTART_EXIT_CODE = 75
REPOSITORY_ROOT_ENVIRONMENT_VARIABLE = "PORTABLE_PIPE_TOOLS_REPO_ROOT"

GitPullCallback = Callable[[Path], GitPullResult]


@dataclass(frozen=True)
class RenderWorkerUpdateResult:
    repository_root: Path
    git_pull: GitPullResult

    @property
    def update_installed(self) -> bool:
        return (
            self.git_pull.commit_before.casefold()
            != self.git_pull.commit_after.casefold()
        )


def resolve_render_worker_repository_root(
    *,
    environment: Mapping[str, str] | None = None,
    module_file: str | Path | None = None,
) -> Path:
    selected_environment = os.environ if environment is None else environment
    configured_root = str(
        selected_environment.get(REPOSITORY_ROOT_ENVIRONMENT_VARIABLE) or ""
    ).strip()
    if configured_root:
        repository_root = Path(configured_root).expanduser()
    else:
        source_file = Path(module_file or __file__).resolve()
        repository_root = source_file.parents[3]

    return Path(os.path.abspath(repository_root))


def update_render_worker_checkout(
    repository_root: str | Path | None = None,
    *,
    git_pull: GitPullCallback = pull_latest_branch,
) -> RenderWorkerUpdateResult:
    selected_root = (
        resolve_render_worker_repository_root()
        if repository_root is None
        else Path(os.path.abspath(Path(repository_root).expanduser()))
    )
    result = git_pull(selected_root)
    return RenderWorkerUpdateResult(
        repository_root=selected_root,
        git_pull=result,
    )
