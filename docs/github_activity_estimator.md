# GitHub activity estimator experiment

The script in `tools/github_activity_estimator.py` estimates daily GitHub-visible
activity for `lennydefect` in the `DefectStudio` organization. It uses commit
committer timestamps and groups each date in `America/Los_Angeles` by default.

## Run it

From the root of this repository in PowerShell:

```powershell
python -m pip install -r tools/requirements-github-activity.txt
python tools/github_activity_estimator.py --start 2026-11-01 --end 2026-11-08 --csv lenny-activity.csv
```

The script uses an existing Git Credential Manager sign-in for GitHub, or reads
`GITHUB_TOKEN` or `GH_TOKEN` from the environment. It never prints or saves the
credential. `--public-only` permits a run without authentication, but that run
cannot report private repository commits. Use `--help` for user, organization,
timezone, and heuristic options.

For Kat, whose commits use both the `KatVolts` GitHub account and the
`Kat Francis` Defect email identity, add the email search:

```powershell
python tools/github_activity_estimator.py --user KatVolts --author-email kat@defect.studio --start 2026-10-26 --end 2026-11-08
```

The script deduplicates commits found by both searches.

## What the estimate means

For each local day, the report shows commit count, first and last commit times,
the time between them, and estimated activity hours. Monday through Friday,
the estimate starts at 09:00 and ends at the day's last commit. `--workday-start`
can change that time. Saturday and Sunday use the original session method:
commit gaps greater than 90 minutes start another session, and each session
contributes its first-to-last interval plus 30 minutes. A weekday whose last
commit is before the assumed start time also uses the session method. Both
session settings are configurable. Holidays are treated as weekdays. A day
with no commits has a blank estimate, because it is not evidence of zero hours
worked.

This is an activity heuristic, not a measure of hours worked. The committer
timestamp can differ from when a commit was pushed. Work without commits is
invisible, and the script does not yet include pull request reviews, issue
comments, or other GitHub events. [GitHub commit search only searches default
branches](https://docs.github.com/en/search-github/searching-on-github/searching-commits),
so work still on another branch may be missing. The script stops if GitHub
reports incomplete or capped search results instead of silently undercounting.
