#!/usr/bin/env python3
"""Estimate daily GitHub-visible activity from commit timestamps.

Example (PowerShell, with Git Credential Manager already signed in):

    python tools/github_activity_estimator.py --start 2026-11-01 --end 2026-11-08

This is an experiment, not a time sheet. Weekdays count from 09:00 to the last
commit; weekends use commit sessions. GitHub commit search covers default
branches only. A commit's committer date is not its push time, and work without
commits is invisible. The script uses GITHUB_TOKEN, GH_TOKEN, or an existing
Git Credential Manager sign-in unless --public-only is specified.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


API_URL = "https://api.github.com/search/commits"
PER_PAGE = 100
SEARCH_RESULT_LIMIT = 1000


@dataclass(frozen=True)
class Commit:
    repository: str
    sha: str
    committed_at: datetime


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use YYYY-MM-DD") from exc


def parse_clock(value: str) -> time:
    try:
        clock = time.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use HH:MM") from exc
    if clock.tzinfo is not None or clock.second or clock.microsecond:
        raise argparse.ArgumentTypeError("use HH:MM without seconds or timezone")
    return clock


def git_credential_token() -> str | None:
    """Read an existing GitHub credential without prompting or printing it."""
    environment = os.environ.copy()
    environment.update({"GCM_INTERACTIVE": "Never", "GIT_TERMINAL_PROMPT": "0"})
    try:
        result = subprocess.run(
            ["git", "-c", "credential.interactive=never", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator and key == "password":
            return value or None
    return None


def github_json(url: str, token: str | None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "defect-github-activity-estimator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            detail = json.load(exc).get("message", "")
        except (ValueError, OSError):
            detail = ""
        limit = exc.headers.get("x-ratelimit-remaining")
        suffix = f" (rate limit remaining: {limit})" if limit is not None else ""
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {detail}{suffix}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach GitHub: {exc.reason}") from exc


def search_commits(
    org: str, user: str, start: date, end: date, timezone: ZoneInfo, token: str | None,
    author_field: str = "author",
) -> list[Commit]:
    if author_field not in {"author", "author-email"}:
        raise ValueError(f"Unsupported author field: {author_field}")
    # The local date range may straddle adjacent UTC dates. Search the whole
    # enclosing UTC date range, then apply exact local-day filtering below.
    utc_start = datetime.combine(start, time.min, timezone).astimezone(UTC).date()
    utc_end = datetime.combine(end + timedelta(days=1), time.min, timezone).astimezone(UTC).date()
    query = f"org:{org} {author_field}:{user} committer-date:{utc_start}..{utc_end}"
    commits: dict[tuple[str, str], Commit] = {}
    expected_count: int | None = None
    page = 1

    while True:
        url = API_URL + "?" + urlencode(
            {"q": query, "sort": "committer-date", "order": "asc", "per_page": PER_PAGE, "page": page}
        )
        response = github_json(url, token)
        if response.get("incomplete_results"):
            raise RuntimeError("GitHub reported incomplete search results; narrow the date range and retry.")
        count = response.get("total_count")
        if not isinstance(count, int):
            raise RuntimeError("GitHub search response has no total_count.")
        if count > SEARCH_RESULT_LIMIT:
            raise RuntimeError(
                f"Search matched {count} commits; narrow the date range to stay below GitHub's "
                f"{SEARCH_RESULT_LIMIT}-result search cap."
            )
        if expected_count is None:
            expected_count = count
        elif count != expected_count:
            raise RuntimeError("GitHub search results changed during pagination; retry the report.")

        items = response.get("items")
        if not isinstance(items, list):
            raise RuntimeError("GitHub search response has no items list.")
        for item in items:
            try:
                repository = item["repository"]["full_name"]
                sha = item["sha"]
                stamp = item["commit"]["committer"]["date"]
                committed_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("A GitHub commit has missing or invalid timestamp data.") from exc
            if committed_at.tzinfo is None:
                raise RuntimeError("A GitHub commit timestamp lacks a timezone.")
            local_day = committed_at.astimezone(timezone).date()
            if start <= local_day <= end:
                commits[(repository, sha)] = Commit(repository, sha, committed_at)

        if page * PER_PAGE >= count:
            break
        if not items:
            raise RuntimeError("GitHub returned an empty page before all results were read.")
        page += 1

    return sorted(commits.values(), key=lambda item: item.committed_at)


def merge_commits(*groups: list[Commit]) -> list[Commit]:
    """Combine author searches without counting the same repository commit twice."""
    unique = {(commit.repository, commit.sha): commit for group in groups for commit in group}
    return sorted(unique.values(), key=lambda item: item.committed_at)


def activity_minutes(stamps: list[datetime], gap_minutes: int, padding_minutes: int) -> tuple[int, float]:
    """Group nearby commits; each session spans first to last plus fixed padding."""
    if not stamps:
        return 0, 0.0
    stamps = sorted(stamps, key=lambda stamp: stamp.astimezone(UTC))
    sessions = 0
    total_minutes = 0.0
    first = last = stamps[0]
    for stamp in stamps[1:]:
        gap = (stamp.astimezone(UTC) - last.astimezone(UTC)).total_seconds() / 60
        if gap > gap_minutes:
            sessions += 1
            total_minutes += (last.astimezone(UTC) - first.astimezone(UTC)).total_seconds() / 60 + padding_minutes
            first = stamp
        last = stamp
    sessions += 1
    total_minutes += (last.astimezone(UTC) - first.astimezone(UTC)).total_seconds() / 60 + padding_minutes
    return sessions, total_minutes


def daily_rows(
    commits: list[Commit], start: date, end: date, timezone: ZoneInfo,
    gap_minutes: int, padding_minutes: int, workday_start: time = time(9),
) -> list[dict[str, str | int | float]]:
    by_day: dict[date, list[datetime]] = {}
    for commit in commits:
        local_time = commit.committed_at.astimezone(timezone)
        by_day.setdefault(local_time.date(), []).append(local_time)

    rows: list[dict[str, str | int | float]] = []
    day = start
    while day <= end:
        stamps = sorted(by_day.get(day, []), key=lambda stamp: stamp.astimezone(UTC))
        sessions: int | str = ""
        minutes = 0.0
        method = ""
        if stamps:
            start_time = datetime.combine(day, workday_start, timezone)
            if day.weekday() < 5 and stamps[-1].astimezone(UTC) >= start_time.astimezone(UTC):
                minutes = (stamps[-1].astimezone(UTC) - start_time.astimezone(UTC)).total_seconds() / 60
                method = "workday start to last"
            else:
                sessions, minutes = activity_minutes(stamps, gap_minutes, padding_minutes)
                method = "weekend sessions" if day.weekday() >= 5 else "early commit fallback"
        rows.append({
            "date": day.isoformat(),
            "commits": len(stamps),
            "first_commit": stamps[0].strftime("%H:%M%z") if stamps else "",
            "last_commit": stamps[-1].strftime("%H:%M%z") if stamps else "",
            "sessions": sessions,
            "activity_span_hours": round((stamps[-1].astimezone(UTC) - stamps[0].astimezone(UTC)).total_seconds() / 3600, 2) if stamps else "",
            "estimated_activity_hours": round(minutes / 60, 2) if stamps else "",
            "method": method,
        })
        day += timedelta(days=1)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--org", default="DefectStudio", help="GitHub organization (default: DefectStudio)")
    parser.add_argument("--user", default="lennydefect", help="GitHub commit author (default: lennydefect)")
    parser.add_argument("--author-email", action="append", default=[], help="also include this commit author email (repeatable)")
    parser.add_argument("--start", type=parse_date, help="first local date, YYYY-MM-DD")
    parser.add_argument("--end", type=parse_date, help="last local date, YYYY-MM-DD")
    parser.add_argument("--timezone", default="America/Los_Angeles", help="IANA timezone for daily grouping")
    parser.add_argument("--workday-start", type=parse_clock, default=time(9), help="weekday start time, HH:MM (default: 09:00)")
    parser.add_argument("--gap-minutes", type=int, default=90, help="fallback: start a new session after this gap (default: 90)")
    parser.add_argument("--padding-minutes", type=int, default=30, help="fallback: minutes added per session (default: 30)")
    parser.add_argument("--csv", type=Path, help="optional CSV output path")
    parser.add_argument("--public-only", action="store_true", help="allow unauthenticated search of public repositories only")
    args = parser.parse_args(argv)

    try:
        timezone = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError:
        parser.error(f"unknown timezone: {args.timezone} (on Windows, run: python -m pip install tzdata)")
    today = datetime.now(timezone).date()
    end = args.end or today
    start = args.start or end - timedelta(days=13)
    if start > end:
        parser.error("--start must be on or before --end")
    if args.gap_minutes <= 0 or args.padding_minutes < 0:
        parser.error("--gap-minutes must be positive and --padding-minutes nonnegative")
    token = None if args.public_only else (
        os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or git_credential_token()
    )
    if not token and not args.public_only:
        parser.error("sign in with Git Credential Manager, set GITHUB_TOKEN or GH_TOKEN, or pass --public-only")

    try:
        groups = [search_commits(args.org, args.user, start, end, timezone, token)]
        for email in args.author_email:
            groups.append(search_commits(args.org, email, start, end, timezone, token, "author-email"))
        commits = merge_commits(*groups)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    rows = daily_rows(commits, start, end, timezone, args.gap_minutes, args.padding_minutes, args.workday_start)

    print(f"GitHub commit activity for {args.user} in {args.org}: {start} through {end} ({args.timezone})")
    if args.author_email:
        print(f"Author matching: GitHub user plus {len(args.author_email)} additional author email(s), deduplicated.")
    print("Coverage: default branches; " + ("token-accessible repositories" if token else "public repositories only"))
    print(f"Method: Mon-Fri {args.workday_start:%H:%M} to last commit; weekends and early-only weekdays: "
          f"{args.gap_minutes}-min session gap + {args.padding_minutes} min/session.")
    print(f"{'Date':10} {'Commits':>7} {'First':>10} {'Last':>10} {'Sessions':>8} {'Span h':>8} {'Estimate h':>10}  Method")
    for row in rows:
        print(f"{row['date']:10} {row['commits']:>7} {row['first_commit'] or '—':>10} "
              f"{row['last_commit'] or '—':>10} {row['sessions'] or '—':>8} "
              f"{row['activity_span_hours'] if row['activity_span_hours'] != '' else '—':>8} "
              f"{row['estimated_activity_hours'] if row['estimated_activity_hours'] != '' else '—':>10}  "
              f"{row['method'] or '—'}")
    print("No commits means no GitHub evidence, not zero hours worked.")
    print("Estimate is a heuristic, not measured work time. Committer dates can differ from push times.")

    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV written to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
