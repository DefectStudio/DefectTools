# Company V2 SQL rollout

The September 15 worker implementation is SQL-only. Operators configure Dropbox,
Unreal and local projects; the company service URL and worker-scoped credential
are included in the internal EXE by the build administrator. The worker has no
connection dialog and never falls back to Dropbox job folders.

## Current verified state

- Separate local service: `defect-farm-api-v2` on `http://127.0.0.1:8795`.
- Separate local SQL database: `defect-farm-v2-local`.
- 220 worker regression tests passed.
- API deployment dry-run passed.
- Copied EXE self-test passed with fresh user settings.
- Packaged `check-setup` authenticated to local V2 SQL and checked Bishop successfully.
- Read-only Cloudflare D1 inventory found no hosted V2 database.

The current preview is a local-development build. It cannot reach this computer's
localhost service from another machine. Company-wide use requires the hosted
service below and a rebuild with that service profile.

## Proposed hosted deployment

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

The earlier instruction to keep V2 local for review has not yet been replaced
with approval to create and deploy these hosted resources.
