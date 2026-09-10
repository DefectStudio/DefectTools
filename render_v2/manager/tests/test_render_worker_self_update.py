from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from portable_pipe_tools.render_farm.git_sync import GitPullResult
from portable_pipe_tools.render_farm.self_update import (
    RENDER_WORKER_RESTART_EXIT_CODE,
    REPOSITORY_ROOT_ENVIRONMENT_VARIABLE,
    resolve_render_worker_repository_root,
    update_render_worker_checkout,
)


class RenderWorkerSelfUpdateTests(unittest.TestCase):
    def _git_result(
        self,
        repository_root: Path,
        *,
        before: str,
        after: str,
    ) -> GitPullResult:
        return GitPullResult(
            repository_root=repository_root,
            branch="main",
            upstream="origin/main",
            commit_before=before,
            commit_after=after,
            summary="Already up to date.",
            transcript="",
        )

    def test_launcher_repository_environment_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            expected_root = Path(temporary_directory)
            resolved = resolve_render_worker_repository_root(
                environment={
                    REPOSITORY_ROOT_ENVIRONMENT_VARIABLE: str(expected_root)
                },
                module_file=(
                    expected_root
                    / "wrong"
                    / "src"
                    / "portable_pipe_tools"
                    / "render_farm"
                    / "self_update.py"
                ),
            )

        self.assertEqual(expected_root, resolved)

    def test_source_layout_falls_back_to_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            expected_root = Path(temporary_directory)
            module_file = (
                expected_root
                / "src"
                / "portable_pipe_tools"
                / "render_farm"
                / "self_update.py"
            )
            resolved = resolve_render_worker_repository_root(
                environment={},
                module_file=module_file,
            )

        self.assertEqual(expected_root, resolved)

    def test_changed_commit_requests_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)

            def fake_pull(selected_root: Path) -> GitPullResult:
                self.assertEqual(repository_root, selected_root)
                return self._git_result(
                    repository_root,
                    before="a" * 40,
                    after="b" * 40,
                )

            result = update_render_worker_checkout(
                repository_root,
                git_pull=fake_pull,
            )

        self.assertTrue(result.update_installed)

    def test_unchanged_commit_does_not_request_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository_root = Path(temporary_directory)
            commit = "a" * 40
            result = update_render_worker_checkout(
                repository_root,
                git_pull=lambda selected_root: self._git_result(
                    selected_root,
                    before=commit.upper(),
                    after=commit,
                ),
            )

        self.assertFalse(result.update_installed)

    def test_gui_launcher_restarts_on_the_documented_exit_code(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        launcher_text = (
            repository_root / "tools" / "render_worker_gui.bat"
        ).read_text(encoding="utf-8")

        self.assertEqual(75, RENDER_WORKER_RESTART_EXIT_CODE)
        self.assertIn(":launch_render_worker", launcher_text)
        self.assertIn(
            'if "%RENDER_WORKER_GUI_EXIT_CODE%"=="75"',
            launcher_text,
        )
        self.assertIn("goto launch_render_worker", launcher_text)
        self.assertIn(
            r'%ProgramFiles%\Git\cmd\git.exe',
            launcher_text,
        )
        self.assertIn("where git.exe >nul 2>&1", launcher_text)


if __name__ == "__main__":
    unittest.main()
