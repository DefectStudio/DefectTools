from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from portable_pipe_tools.render_farm.git_sync import (
    GitPullError,
    pull_latest_branch,
    write_git_pull_log,
)


class GitPullTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository_root = Path(self.temporary_directory.name)
        self.commit_before = "a" * 40
        self.commit_after = "b" * 40

    def test_clean_checkout_pulls_and_verifies_latest_upstream(self) -> None:
        expected = [
            (["rev-parse", "--show-toplevel"], str(self.repository_root)),
            (["branch", "--show-current"], "main"),
            (["status", "--porcelain", "--untracked-files=all"], ""),
            (["rev-parse", "HEAD"], self.commit_before),
            (
                [
                    "rev-parse",
                    "--abbrev-ref",
                    "--symbolic-full-name",
                    "@{upstream}",
                ],
                "origin/main",
            ),
            (["pull", "--ff-only"], "Updating aaaaaaa..bbbbbbb\nFast-forward"),
            (["status", "--porcelain", "--untracked-files=all"], ""),
            (["rev-parse", "HEAD"], self.commit_after),
            (
                [
                    "rev-list",
                    "--left-right",
                    "--count",
                    "HEAD...origin/main",
                ],
                "0\t0",
            ),
        ]
        calls: list[list[str]] = []

        def fake_runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            del kwargs
            arguments = command[3:]
            calls.append(arguments)
            expected_arguments, stdout = expected[len(calls) - 1]
            self.assertEqual(expected_arguments, arguments)
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        result = pull_latest_branch(
            self.repository_root,
            command_runner=fake_runner,
        )

        self.assertEqual("main", result.branch)
        self.assertEqual("origin/main", result.upstream)
        self.assertEqual(self.commit_before, result.commit_before)
        self.assertEqual(self.commit_after, result.commit_after)
        self.assertEqual("Fast-forward", result.summary)
        self.assertEqual(len(expected), len(calls))

        log_path = self.repository_root / "git_pull.log"
        write_git_pull_log(log_path, result)
        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn("$ git pull --ff-only", log_text)
        self.assertIn("Fast-forward", log_text)

    def test_dirty_checkout_is_rejected_before_pull(self) -> None:
        responses = [
            (0, str(self.repository_root), ""),
            (0, "main", ""),
            (0, " M Content/Shot.uasset", ""),
        ]
        calls: list[list[str]] = []

        def fake_runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            del kwargs
            calls.append(command[3:])
            return_code, stdout, stderr = responses[len(calls) - 1]
            return subprocess.CompletedProcess(
                command,
                return_code,
                stdout=stdout,
                stderr=stderr,
            )

        with self.assertRaisesRegex(GitPullError, "local or untracked changes"):
            pull_latest_branch(
                self.repository_root,
                command_runner=fake_runner,
            )

        self.assertNotIn(["pull", "--ff-only"], calls)

    def test_failed_fast_forward_reports_git_error(self) -> None:
        responses = [
            (0, str(self.repository_root), ""),
            (0, "main", ""),
            (0, "", ""),
            (0, self.commit_before, ""),
            (0, "origin/main", ""),
            (1, "", "fatal: Not possible to fast-forward, aborting."),
        ]
        call_index = 0

        def fake_runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
            nonlocal call_index
            del kwargs
            return_code, stdout, stderr = responses[call_index]
            call_index += 1
            return subprocess.CompletedProcess(
                command,
                return_code,
                stdout=stdout,
                stderr=stderr,
            )

        with self.assertRaisesRegex(GitPullError, "Not possible to fast-forward"):
            pull_latest_branch(
                self.repository_root,
                command_runner=fake_runner,
            )


if __name__ == "__main__":
    unittest.main()
