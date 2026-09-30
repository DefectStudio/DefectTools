# Worker-initiated claiming in V2

Run the V2 worker, configure the engine and project registrations, and click **Start Worker**.
V2 uses only its company SQL dispatcher; there is no coordination-mode switch or
connection button. The Python distribution includes the company worker profile.
The worker stays stopped on application launch. Its name defaults to the machine
name plus `-V2`; name, polling interval, and render timeout
persist after starting. **Stop Worker** interrupts the current render and stops
polling. The existing retry/blacklist behavior handles unsuccessful jobs.

## Dropbox is storage, not coordination

Dropbox provides the show catalog, shared files and output/log destinations.
The V2 worker never scans `01_NeedsRendering` or renames folders to claim work.
Missing SQL configuration or a service outage is an error, not a filesystem
fallback. Historical filesystem helpers remain only for legacy compatibility tests.

## SQL claims

The worker requests `/api/v1/jobs/claim`, including an explicit
`eligible_project_ids` list and `capabilities.registered_projects`. The V2
dispatcher applies that list inside its atomic claim SQL. It retains priority,
FIFO ordering, blacklists, lease renewal, stop requests, and completion receipts.
An empty list claims nothing. Malformed lists are rejected. Repeated requests
return the existing eligible lease; a removed project cannot be returned as an
eligible active claim. The older request format without a list retains its
existing behavior for compatibility; the registered V2 worker always supplies
a list and also rejects/releases an unexpected ineligible response.

For every claimed job, the worker resolves the local `.uproject` and Dropbox
renderFarm root from that show's registration. That root controls output mapping
and published render logs, including when the job is for a show other than the
first registration. It uses the minimal managed Unreal runtime and a project
lock. Before each render it pulls the registered project's current branch from
its upstream using fast-forward only, updates the project's pinned submodules,
and downloads LFS assets. Updates run while the SQL lease is maintained. Failed
updates do not launch Unreal and follow the existing job-failure policy. Stop
cancels the update process. Missing-project cloning, repository discovery and
main-project branch switching do not run. Git command logs are in the job's
`project-sync/logs` folder; the pulled commit is recorded in job/result metadata.

The packaged worker reads its embedded company V2 profile. Source development
uses `%LOCALAPPDATA%/DefectStudio/RenderFarmV2/cloud_connection.json`, separate
from V1 credentials. No SQL schema migration is needed for eligibility. The local
V2 dispatcher is v0.7.0 on port 8795. The released EXE now uses the separate
hosted V2 company service. See [deployment details](company-sql-deployment.md);
localhost builds are for local development only.

## Historical validation — September 10, 2026 (filesystem mode since removed)

- Filesystem integration: eligible priority selection across two shows,
  unregistered and unavailable projects left queued, Stop before claim,
  failure/requeue, and no project Git update.
- Cloud integration: project filtering, empty lists, two workers racing for one
  job, active lease replay, heartbeat, completion, and resolving a nonfirst show.
- Existing V1-compatible API smoke checks and worker regression tests pass.
- GUI Start/Stop and project-edit locking are tested with background polling.
- Real Bishop shot `ZZZ_000_0850` was submitted to the isolated local test API
  on port 8796, claimed by `BISHOP-V2-LOCAL-VALIDATION`, rendered from
  `F:/Projects/s3bishop.uproject`, and reported **complete** to SQL. All **40 EXRs**
  were produced with downloads off. Job: `bishop_registered_claim_f854ab7a56f6`.
- Machine-local evidence is in
  `LocalSaveFiles/cloud-claim-validation/validation-result.json`; rendered files
  are beneath its `shows/s3bishop/Validation` directory. These are ignored files.

The test dispatcher/database on 8796 was isolated from the normal local V2
database on 8795 and from V1 production. That validation used the local V2
backend and performed no production deployment. The subsequent September 15
hosted V2 deployment is documented separately above.

To repeat the API eligibility checks, start an isolated local dispatcher, then
run `node scripts/test-project-claims.mjs` in the V2 API directory. It defaults
to localhost:8796 and refuses non-local destinations. Worker regression tests
remain available through `test_worker.bat --no-pause`.
