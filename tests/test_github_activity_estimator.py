"""Checks for the experimental commit-to-activity heuristic."""

import sys
import subprocess
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from github_activity_estimator import (  # noqa: E402
    Commit, activity_minutes, daily_rows, git_credential_token, merge_commits, search_commits,
)


class ActivityEstimateTests(unittest.TestCase):
    def test_long_gap_starts_another_session(self):
        stamps = [
            datetime(2026, 11, 4, 9, 0, tzinfo=UTC),
            datetime(2026, 11, 4, 9, 30, tzinfo=UTC),
            datetime(2026, 11, 4, 12, 0, tzinfo=UTC),
        ]
        sessions, minutes = activity_minutes(stamps, gap_minutes=90, padding_minutes=30)
        self.assertEqual(sessions, 2)
        self.assertEqual(minutes, 90)

    def test_local_midnight_splits_days_and_missing_day_is_blank(self):
        tz = ZoneInfo("America/Los_Angeles")
        commits = [
            Commit("DefectStudio/ironwidow", "a", datetime(2026, 11, 5, 7, 45, tzinfo=UTC)),
            Commit("DefectStudio/ironwidow", "b", datetime(2026, 11, 5, 8, 15, tzinfo=UTC)),
        ]
        rows = daily_rows(commits, date(2026, 11, 4), date(2026, 11, 6), tz, 90, 30)
        self.assertEqual([row["commits"] for row in rows], [1, 1, 0])
        self.assertEqual([row["first_commit"] for row in rows], ["23:45-0800", "00:15-0800", ""])
        self.assertEqual([row["estimated_activity_hours"] for row in rows], [14.75, 0.5, ""])
        self.assertEqual([row["method"] for row in rows], ["workday start to last", "early commit fallback", ""])

    def test_daylight_saving_fall_back_uses_elapsed_time(self):
        tz = ZoneInfo("America/Los_Angeles")
        commits = [
            Commit("DefectStudio/ironwidow", "a", datetime(2026, 11, 1, 8, 30, tzinfo=UTC)),
            Commit("DefectStudio/ironwidow", "b", datetime(2026, 11, 1, 9, 30, tzinfo=UTC)),
        ]
        row = daily_rows(commits, date(2026, 11, 1), date(2026, 11, 1), tz, 90, 30)[0]
        self.assertEqual(row["first_commit"], "01:30-0700")
        self.assertEqual(row["last_commit"], "01:30-0800")
        self.assertEqual(row["sessions"], 1)
        self.assertEqual(row["activity_span_hours"], 1.0)
        self.assertEqual(row["estimated_activity_hours"], 1.5)
        self.assertEqual(row["method"], "weekend sessions")

    def test_weekday_counts_from_nine_to_last_commit_even_with_long_gap(self):
        tz = ZoneInfo("America/Los_Angeles")
        commits = [
            Commit("DefectStudio/ironwidow", "a", datetime(2026, 11, 2, 21, 0, tzinfo=UTC)),
            Commit("DefectStudio/ironwidow", "b", datetime(2026, 11, 3, 1, 0, tzinfo=UTC)),
        ]
        row = daily_rows(commits, date(2026, 11, 2), date(2026, 11, 2), tz, 90, 30)[0]
        self.assertEqual(row["estimated_activity_hours"], 8.0)
        self.assertEqual(row["method"], "workday start to last")
        self.assertEqual(row["sessions"], "")

    def test_weekend_retains_session_fallback(self):
        tz = ZoneInfo("America/Los_Angeles")
        commits = [
            Commit("DefectStudio/ironwidow", "a", datetime(2026, 11, 1, 21, 0, tzinfo=UTC)),
            Commit("DefectStudio/ironwidow", "b", datetime(2026, 11, 2, 1, 0, tzinfo=UTC)),
        ]
        row = daily_rows(commits, date(2026, 11, 1), date(2026, 11, 1), tz, 90, 30)[0]
        self.assertEqual(row["estimated_activity_hours"], 1.0)
        self.assertEqual(row["method"], "weekend sessions")

    def test_early_only_weekday_uses_fallback(self):
        tz = ZoneInfo("America/Los_Angeles")
        commits = [Commit("DefectStudio/ironwidow", "a", datetime(2026, 11, 5, 8, 15, tzinfo=UTC))]
        row = daily_rows(commits, date(2026, 11, 5), date(2026, 11, 5), tz, 90, 30)[0]
        self.assertEqual(row["estimated_activity_hours"], 0.5)
        self.assertEqual(row["method"], "early commit fallback")

    def test_search_uses_github_shape_and_filters_by_local_date(self):
        def item(sha, stamp):
            return {
                "repository": {"full_name": "DefectStudio/ironwidow"},
                "sha": sha,
                "commit": {"committer": {"date": stamp}},
            }

        payload = {
            "total_count": 2,
            "incomplete_results": False,
            "items": [item("a", "2026-11-05T07:45:00Z"), item("b", "2026-11-05T08:15:00Z")],
        }
        with patch("github_activity_estimator.github_json", return_value=payload) as request:
            commits = search_commits(
                "DefectStudio", "lennydefect", date(2026, 11, 4), date(2026, 11, 4),
                ZoneInfo("America/Los_Angeles"), "sample-token",
            )
        self.assertEqual([commit.sha for commit in commits], ["a"])
        self.assertIn("author%3Alennydefect", request.call_args.args[0])

    def test_additional_author_email_uses_email_qualifier(self):
        payload = {"total_count": 0, "incomplete_results": False, "items": []}
        with patch("github_activity_estimator.github_json", return_value=payload) as request:
            search_commits(
                "DefectStudio", "kat@defect.studio", date(2026, 11, 4), date(2026, 11, 4),
                ZoneInfo("America/Los_Angeles"), "sample-token", "author-email",
            )
        self.assertIn("author-email%3Akat%40defect.studio", request.call_args.args[0])

    def test_author_searches_deduplicate_the_same_commit(self):
        first = Commit("DefectStudio/ironwidow", "a", datetime(2026, 11, 4, 20, 0, tzinfo=UTC))
        second = Commit("DefectStudio/ironwidow", "b", datetime(2026, 11, 4, 21, 0, tzinfo=UTC))
        self.assertEqual(merge_commits([first], [first, second]), [first, second])

    def test_existing_git_credential_is_read_without_prompt(self):
        result = subprocess.CompletedProcess([], 0, "username=example\npassword=sample-secret\n", "")
        with patch("github_activity_estimator.subprocess.run", return_value=result) as run:
            self.assertEqual(git_credential_token(), "sample-secret")
        self.assertEqual(run.call_args.kwargs["env"]["GCM_INTERACTIVE"], "Never")
        self.assertEqual(run.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")


if __name__ == "__main__":
    unittest.main()
