# Separate V1 and V2 installations

The September 10 transition direction is to keep the original manager and worker available while developing V2 independently. V2 must never share V1's live queue or apply migrations to V1's database.

| Component | V1 | V2 |
| --- | --- | --- |
| Manager | `F:/Defect Tools/tools/farm_render_manager.bat` | `F:/RenderFarmManager/run_manager_v2.bat` |
| Worker | `F:/Defect Tools/tools/render_worker.bat` | `F:/RenderWorker/run_worker_v2_gui.bat` |
| Dispatcher | Existing production `defect-farm-api` | Local `defect-farm-api-v2` on port 8795 |
| SQL | Existing production `defect-farm-production` | Independent local `defect-farm-v2-local` |
| V2 database files | Not applicable | `F:/RenderFarmManager/LocalSaveFiles/v2-backend` |

The manager registry implementation was copied into the separate local V2 repository before its changes were reverted in `F:/Defect Tools`. The original manager, shared client, API, and migrations match their pre-registry versions. Other pre-existing uncommitted work in the original repository was preserved.

Both V2 clients default to localhost for read-only access and reject the known V1 production dispatcher hostname for all roles. The V2 manager launcher supplies local test credentials for its own process; it does not copy V1 credential files. V2 retains the manager registry, and the independent worker retains its GUI and manually registered project list.

Start `run_v2_backend.bat` in the manager repository, then `run_manager_v2.bat`. The backend launcher applies only local migrations and runs the local service. The manager and worker remain separate apps with separate settings. The worker's SQL-backed dropdown and project eligibility integration remain later steps.

No V2 production resources have been created or deployed. The database ID in the V2 Wrangler configuration is a placeholder for local development. Hosting V2 later requires a new service and new database, followed by an explicitly planned transition. Do not reuse V1's resource IDs, endpoint, tokens, or queue.

The old local registry demo data in `F:/Defect Tools/LocalSaveFiles/project-registry-validation` is retained as a development artifact. The new V2 database starts separately. No production data was copied, modified, or removed.

## Verification

- Original V1 manager, shared dispatcher client, and backend match commit `2270903` after reverting the misplaced registry feature in commit `eab173e`.
- Independent V2 manager suite: 320 tests passed. One initial parallel run encountered a transient Windows heartbeat file lock; an isolated rerun passed.
- V2 worker suite: 169 tests passed, including rejection of V1 service connections.
- Separate V2 local API: 24 registry checks and the existing job/lease smoke test passed. Health identifies `defect-farm-api-v2` in `v2-local`.
- The manager repository has no remote, and no production deployment or migration was performed.
