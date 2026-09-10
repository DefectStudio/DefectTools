# Worker-initiated claiming in V2

Run the root `run_worker_v2.bat`, configure the engine and project registrations,
choose **Use Cloud Dispatcher** as appropriate, and click **Start Worker**.
The worker stays stopped on application launch. Its name defaults to the machine
name plus `-V2`; name, coordination choice, polling interval, and render timeout
persist after starting. **Stop Worker** interrupts the current render and stops
polling. The existing retry/blacklist behavior handles unsuccessful jobs.

## Filesystem mode

The worker scans only explicitly registered shows' `renderFarm/01_NeedsRendering`
folders. It skips packages belonging to other shows and registrations whose
local project or renderFarm folder is unavailable. Across these shows it compares
the next eligible jobs using V1's priority/age ordering, then claims through V1's
directory rename into `02_IsRendering`. The manager does not select or push jobs.

These are the configured filesystem queues: selecting the same renderFarm root
as V1 means competing for that same queue. Development validation uses isolated
test directories; no listener was started against the team's Dropbox queues.

## Cloud mode

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
lock. Project downloads, repository discovery, fetch, pull, and branch switching
do not run in this local-registration workflow.

V2 cloud connection settings are stored under
`%LOCALAPPDATA%/DefectStudio/RenderFarmV2/cloud_connection.json`, separate from
V1's `RenderFarm` credentials. No SQL schema migration is needed for eligibility.
The local V2 dispatcher is v0.7.0, started by root `run_v2_backend.bat` on port
8795. Hosted V2 deployment and packaging/startup recovery remain future work.

## Validation — September 10, 2026

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
database on 8795 and from V1 production. The normal local backend now runs from
the consolidated repository. The updated GUI is left stopped, configured for
that local V2 backend; nothing was deployed to production.

To repeat the API eligibility checks, start an isolated local dispatcher, then
run `node scripts/test-project-claims.mjs` in the V2 API directory. It defaults
to localhost:8796 and refuses non-local destinations. Worker regression tests
remain available through `test_worker.bat --no-pause`.
