# Defect Render Farm Cloud Dispatcher

## Production resources

- Worker API: `https://defect-farm-api.twilight-tooth-7b7c.workers.dev`
- D1 database: `defect-farm-production`
- D1 binding: `DB`
- API version: `v1`
- Worker lease: 5 minutes, renewed every 60 seconds during an Unreal render
- Preview URLs: disabled

The Cloudflare Worker and D1 database coordinate metadata, leases, retries,
blacklists, and worker stop requests. Dropbox continues to carry `job.json`,
render diagnostics, Unreal logs, EXRs, and MP4s.

## Security

Three independent bearer keys are used:

- `submit`: may add jobs from Unreal.
- `worker`: may claim, heartbeat, complete, fail, or release jobs.
- `manager`: may list or delete jobs, clear blacklists, replace failed jobs,
  and request stops.

Keys are encrypted at rest by Cloudflare and are never committed to Git. On a
Windows computer, the matching local keys are stored in:

`%LOCALAPPDATA%\DefectStudio\RenderFarm\cloud_connection.json`

The administrator's copy is ACL-restricted to that Windows user. Distribute
only the role key a computer needs, using a secure private channel.

## Configure a computer

Run `configure_cloud_dispatcher.bat` from the DefectTools repository.

1. Leave the production API URL unchanged.
2. Select `Render Worker`, `Unreal Submitter`, or `Farm Manager`.
3. Paste only that role's key.
4. Select **Verify and Save**.

The setup window calls a read-only authentication endpoint and refuses a key
for the wrong role. It does not display previously saved keys.

## Safe rollout order

1. Commit and push the DefectTools and `s3bishop` changes together.
2. Allow every employee Render Worker to complete its startup self-update.
3. Configure the `Render Worker` key on every participating computer.
4. Confirm **Use Cloud Dispatcher** is checked in every Render Worker.
5. Submit one harmless real farm job and confirm one worker claims it.
6. After that passes, submit the production queue from Unreal.

Do not submit D1-coordinated jobs while an old, unupdated worker is running.
Updated filesystem-mode workers deliberately skip jobs marked
`dispatcher_coordination: cloud`, but old builds do not know that marker.

## Reliability behavior

- D1 grants a job to exactly one worker with an atomic conditional update.
- A worker cannot hold two active leases.
- After its startup Git/update check succeeds, the Render Worker automatically
  starts listening for jobs. An installed self-update restarts the app, which
  performs the same check and resumes listening without a manual button press.
- Claim retries use stable request IDs and return the original lease.
- Missing Dropbox packages cause a clean release, not a blacklist.
- Render failures requeue the job and blacklist only the failing worker.
- Completion, failure, release, submission, and manager resubmission are safe to
  retry after a lost HTTP response.
- Manager deletion is idempotent and refuses to delete a job while it is
  rendering. The Dropbox package is removed only after D1 confirms deletion.
- Manager resubmission atomically inserts the fresh D1 job and deletes the old
  non-rendering D1 job. The old Dropbox package is removed only after D1
  explicitly confirms that replacement.
- The worker writes `dispatcher_update_pending.json` before finalizing the
  Dropbox package. Another worker can deliver that pending update after a crash
  or internet outage without rendering the job again.
- `dispatcher_submission.json` records successful Unreal/manager registration.

## Current manager transition

Farm Render Manager still reads job packages and logs from Dropbox so the
existing interface remains intact. When its manager key is configured, Delete,
Clear Blacklist, Resubmit, and STOP update the Cloud Dispatcher as well as the
local Dropbox representation. Delete removes D1 first and removes the Dropbox
job package only after cloud confirmation; rendered MP4 and EXR outputs are not
deleted. Resubmit creates the replacement first, then removes the old failed job
from both D1 and `04_RenderFailed`. Legacy pre-D1 jobs continue to work.

## Rollback

Stop new Unreal submissions first and allow already queued D1 jobs to drain.
Then uncheck **Use Cloud Dispatcher** on the workers. Do not switch a live cloud
job to filesystem coordination mid-render.

## Verification completed

- Local D1 migration and TypeScript compile checks passed.
- Local API smoke tests covered authentication, atomic two-worker claims,
  heartbeats, retry blacklists, completion, release, clear blacklist,
  atomic replacement/deletion, rendering-job protection, and idempotent retries.
- 81 Render Worker and Farm Manager regression/integration tests passed.
- Production read-only checks confirmed the Worker, D1 binding, manager query,
  and all three role keys. Production contained zero jobs and zero workers at
  that checkpoint.
- An approved synthetic production claim race passed on August 16, 2026. Worker
  A intentionally failed, Worker B reclaimed the job, and the job completed on
  attempt 2. Its exact job, attempt, event, blacklist, and fake-worker records
  were then deleted; production was verified clean at zero rows afterward.
