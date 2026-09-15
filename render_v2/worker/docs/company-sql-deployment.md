# Company V2 SQL rollout

The September 15 worker implementation is SQL-only. Operators configure Dropbox,
Unreal and local projects; the company service URL and worker-scoped credential
are included in the internal EXE by the build administrator. The worker has no
connection dialog and never falls back to Dropbox job folders.

## Hosted service — deployed September 15, 2026

- API: `https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev`
- Cloudflare Worker: `defect-farm-api-v2`, environment `v2-production`.
- D1 database: `defect-farm-v2-production`.
- Database ID: `2d3669f5-5114-4a50-9a9c-69463f9e7b48`.
- Deployed API version ID: `56ce64ec-da15-47d9-9c34-7b637167382a`.
- All three migrations applied: initial queue/worker schema, idempotent resubmit,
  and project registry. Application tables are `jobs`, `workers`, `job_attempts`,
  `job_events`, `job_blacklist`, and `projects`.
- Health reports the production V2 database connected. Worker, manager,
  submitter and viewer role authentication passed.
- Hosted SQL lifecycle tests passed: atomic competing claims, retries,
  heartbeat/stop, completion, resubmission and deletion. The test jobs and five
  test worker rows were removed afterward.
- Copied production EXE self-test and authenticated Bishop setup passed.
- Manager company-profile authentication and queue reads passed; 34 targeted
  manager tests passed.

The release EXE now contains the hosted URL and only the worker credential.
The normal `render_v2/manager/run_manager_v2.bat` opens the company SQL manager;
`run_manager_v2_local.bat` retains the isolated local development mode.
Private role profiles and service credentials live outside Git in
`%LOCALAPPDATA%/DefectStudio/RenderFarmV2/company-*.json`.

## Previous local verification

- Separate local service: `defect-farm-api-v2` on `http://127.0.0.1:8795`.
- Separate local SQL database: `defect-farm-v2-local`.
- 220 worker regression tests passed.
- API deployment dry-run passed.
- Copied EXE self-test passed with fresh user settings.
- Packaged `check-setup` authenticated to local V2 SQL and checked Bishop successfully.
- Before deployment, read-only Cloudflare D1 inventory found no hosted V2 database.

Localhost builds remain development-only. The current release has been rebuilt
with the hosted company profile and does not use localhost.

## Deployment procedure used

1. Create a new Cloudflare D1 database named `defect-farm-v2-production`.
2. Use a separate production Wrangler configuration for the existing V2 API
   source under `render_v2/manager/cloudflare/defect-farm-api`. Bind only the new
   database ID; retain the current local configuration for development.
3. Apply the V2 API's existing SQL migrations to that new, empty database.
4. Generate new V2 submitter, worker, manager and viewer credentials. Store them
   as service secrets and in administrator-managed files outside Git.
5. Deploy the new Worker service `defect-farm-api-v2` and verify its health,
   database binding and role authentication.
6. Build RenderWorkerV2.exe with `-CompanyConnection` pointing to a private
   profile containing the hosted service URL and only the V2 worker credential.
7. Repeat the copied-EXE and authenticated setup checks. Use a dedicated test job
   to verify SQL claiming and completion before enabling unattended workers.

No V1 database IDs, credentials, jobs or services are reused or modified. No
production data is copied. The hosted database starts empty; manager/submission
clients must use the same new V2 service before they can supply jobs to it.

The user approved creating the separate hosted V2 service on September 15.
Cloudflare authorization was refreshed before provisioning. V1 resources were
not modified. Future deployments use `wrangler.production.jsonc`; local
development continues to use `wrangler.jsonc`.
