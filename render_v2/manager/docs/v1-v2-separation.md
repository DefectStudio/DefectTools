# Separate V1 and V2 installations

The September 10 transition direction is to keep the original manager and worker available while developing V2 independently. V2 must never share V1's live queue or apply migrations to V1's database.

| Component | V1 | V2 |
| --- | --- | --- |
| Manager | `F:/Defect Tools/tools/farm_render_manager.bat` | `F:/Defect Tools/render_v2/manager/run_manager_v2.bat` |
| Worker | `F:/Defect Tools/tools/render_worker.bat` | `F:/Render Worker V2 Preview/release/RenderWorkerV2.exe` |
| Dispatcher | Existing production `defect-farm-api` | Hosted `defect-farm-api-v2` |
| SQL | Existing production `defect-farm-production` | Independent `defect-farm-v2-production` |
| Local development | Unchanged | Port 8795, `defect-farm-v2-local` |

The manager registry implementation was copied into the separate local V2 repository before its changes were reverted in `F:/Defect Tools`. The original manager, shared client, API, and migrations match their pre-registry versions. Other pre-existing uncommitted work in the original repository was preserved.

Both V2 clients reject the known V1 production dispatcher hostname for all roles. The normal manager launcher reads its private company-manager profile; the released worker embeds only the company-worker profile. These use fresh V2 credentials. Projects are selected from Dropbox and manually registered on each worker.

For local development, start `run_v2_backend.bat`, then `run_manager_v2_local.bat` in the consolidated manager directory. The backend launcher applies only local migrations. The manager and worker remain separate apps with separate settings; workers claim only jobs for their registered projects.

On September 15, the user authorized creation and deployment of the separate V2 company service. `wrangler.production.jsonc` binds the new database; `wrangler.jsonc` retains the local placeholder. See [deployment details](../../worker/docs/company-sql-deployment.md). Do not reuse V1's resource IDs, endpoint, tokens, or queue.

The old local registry demo data in `F:/Defect Tools/LocalSaveFiles/project-registry-validation` is retained as a development artifact. The new V2 database starts separately. No production data was copied, modified, or removed.

## Historical separation verification

- Original V1 manager, shared dispatcher client, and backend match commit `2270903` after reverting the misplaced registry feature in commit `eab173e`.
- Independent V2 manager suite: 320 tests passed. One initial parallel run encountered a transient Windows heartbeat file lock; an isolated rerun passed.
- V2 worker suite: 169 tests passed, including rejection of V1 service connections.
- Separate V2 local API: 24 registry checks and the existing job/lease smoke test passed. Health identifies `defect-farm-api-v2` in `v2-local`.
- No production deployment or migration was performed during the original separation. The later hosted V2 deployment is documented above.
