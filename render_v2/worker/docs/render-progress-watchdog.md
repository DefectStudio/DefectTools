# Render progress and stalled-job recovery

V2 renders have no total-duration limit by default. A job can render for many
hours as long as Movie Render Graph keeps advancing. The former saved two-hour
Give Up timer is not reused as an inactivity setting.

The worker GUI saves three independent controls, in minutes:

| Control | Default | What keeps it alive |
| --- | --- | --- |
| No Render Progress | 10 | Advancing render frames, subsamples, warmup work or a new render stage |
| Startup / Loading Limit | 30 | Separate allowance from Unreal launch until render work begins |
| Finalization Stall Limit | 30 | Finalization transitions or growth of this job's enabled output files |

Each control accepts 1–1440 minutes. A single expensive sample can take longer
than a short allowance; increase the setting for those jobs. Repeated log lines,
unchanged status receipts, timestamps and network heartbeats never reset the
inactivity deadline. Project Git/LFS preparation remains outside these Unreal
render deadlines and retains its existing cancellation and disk-space rules.

## Reporting

The managed RenderWorkerRuntime executor samples MRG on its game-thread frame
callback and writes an atomic `unreal_progress.json` in the attempt's local
control package. Changed snapshots are limited to one write per second;
explicit startup/finalization/completion transitions publish immediately.
Unreal does not perform network calls from this callback.

The external worker reads and validates the job/attempt identity, tracks actual
counter advances using a monotonic clock, and includes the latest percentage
and structured details in its existing job-lease heartbeat once every 60 seconds.
Lease-recovery retries can happen sooner after a network failure. They do not
constitute render progress. The manager's refresh interval defaults to a minute;
a longer selected refresh interval delays what its table displays.

The manager shows percentage and current/total render-frame position. Selected
job details include phase, sequence frame, elapsed time, progress age at the
last check-in, and server receipt time. MRG frame counters represent rendering
position/submitted work, not verified files on disk. Existing final output
validation remains required before marking a job complete.

## Stalls

On expiry the worker terminates only the Unreal process it launched, escalating
to kill if necessary. After confirming process exit it reports an ordinary
retryable failure. The V2 dispatcher blacklists that worker for that job and
requeues the job for another eligible worker; the listener can continue with
other jobs. Logs, final progress receipt and failure reason remain available.
This does not add a GPU-capacity claim filter: another worker is eligible based
on existing registration and blacklist rules, not necessarily higher VRAM.

If the OS cannot confirm Unreal has exited, the worker instead blocks the job
with a non-retryable failure and stops automatic listening. An operator must
close the process or restart the node, then resubmit/clear the failed job as
appropriate. It must not hand off a job while the old process may still write.
Validated completed output can still be accepted if only engine shutdown hung.

The monitor requires the V2 managed runtime. Legacy executor paths retain their
existing total timeout rather than silently inheriting a receipt they cannot
produce. Registry TDR values, render graphs, texture settings and GPU drivers
are not changed by this feature.

## Rollout and compatibility

Percentage updates use the existing hosted API. Structured manager details need
V2 API migration `0004_render_progress.sql` and its matching API implementation,
plus the updated manager client. Older APIs ignore the extra structured field
and still accept percentage updates. Follow the V2 API README using only
`wrangler.production.jsonc`; never apply these changes to V1 resources.

Publish tested source after preparing the V2 service. Workers update on opening
or their existing idle update check, then install the current managed runtime
during the next registered render. Running attempts keep their existing code.
Restart the manager to load its new table/detail formatting.

Registered `render` and `claim-once` CLI commands accept
`--no-progress-timeout`, `--startup-timeout`, and `--finalization-timeout` in
seconds. Their optional `--timeout` retains an explicitly requested total limit;
omitting it leaves total duration unlimited.

Unit tests exercise multi-hour healthy jobs with virtual time, frozen counters,
stale attempts and regressions, output growth, one-minute reporting, process
termination, per-job failure handoff and blocked-process quarantine. A real
5080 render is still needed after deployment to validate that node end to end.
