# Shared project registry

**Superseded September 10, 2026:** V2 now uses the exact Dropbox show folder
names. The manager's create/edit registry UI has been removed. See
[Dropbox projects](dropbox-projects.md) for current setup. The SQL/API prototype
below is historical, unused by either V2 GUI, and has never been deployed to V1.

Implemented September 10, 2026. This code now lives in the independent V2 manager repository. V1 was restored. See [V1/V2 separation](v1-v2-separation.md). Do not apply these migrations or deploy this API to the V1 production resources.

## Manager controls

Open **Projects…** in the Farm Render Manager toolbar, or **Tools → Projects...**. The window loads the shared project list from the dispatcher. **Create project…** creates an ID and display name. Double-click an existing row or choose **Edit selected…** to change its name or active status. Successful saves refresh the list and add the registered IDs to the manager's project filter.

Project IDs are stable identifiers, using lowercase letters, numbers, underscores or hyphens, up to 64 characters. Names can change without changing IDs. To introduce a different ID, create a new entry and deactivate the previous one. IDs are not automatically inferred from job history or existing project filenames.

Inactive projects remain visible to managers and can be reactivated. Worker, submitter, and viewer list requests return active projects only. Manager credentials are required to create or edit; a manager app with only a worker/viewer connection presents a read-only list.

Editing uses a revision number to detect conflicting manager changes. Failed requests preserve the editor's input. Network requests run outside the GUI thread.

## SQL and API

Migration `cloudflare/defect-farm-api/migrations/0003_projects.sql` adds:

| Column | Meaning |
| --- | --- |
| `project_id` | Stable case-insensitive primary key |
| `display_name` | Human-readable project/show name |
| `active` | Whether the project appears in worker lists |
| `revision` | Version used to prevent overwriting concurrent edits |
| `created_at`, `updated_at` | UTC timestamps |

| Route | Permission | Behavior |
| --- | --- | --- |
| `GET /api/v1/projects` | Manager, worker, viewer, submitter | List active projects |
| `GET /api/v1/projects?include_inactive=true` | Manager | List active and inactive projects |
| `POST /api/v1/projects` | Manager | Create from `project_id`, `display_name`, optional `active` |
| `PUT /api/v1/projects/{project_id}` | Manager | Update `display_name`, `active`, and the expected `revision` |

POST replays of the same values return the existing row; conflicting duplicates return 409. PUT replays immediately following a successful identical update return the saved row; stale conflicting updates return 409. Unknown IDs return 404. No delete route is exposed.

The SQL migration adds a table and index only. It does not seed projects, rewrite jobs, rename existing project identifiers, or change job claims. Deactivation controls registry visibility; it does not cancel jobs or yet prevent already-configured workers from claiming them.

Workers will consume the read endpoint through the existing HTTP dispatcher client. They will not need SQL credentials. Connecting that endpoint to the V2 worker dropdown and enforcing registered-project eligibility in job claims are the next steps; the current worker GUI and claim behavior remain unchanged.

## Local review

With the local dispatcher running at `http://127.0.0.1:8795`, run `tools/project_registry_local_demo.bat`. This opens the full manager with the project-registry window. It uses localhost-only test tokens and separate settings; it does not use the production connection. Entries created here are test data in the isolated local database.

To reproduce the local API setup, from `cloudflare/defect-farm-api`:

```powershell
npx wrangler d1 migrations apply defect-farm-v2-local --local --persist-to '../../LocalSaveFiles/v2-backend'
npx wrangler dev --local --ip 127.0.0.1 --port 8795 --persist-to '../../LocalSaveFiles/v2-backend' --var ENVIRONMENT:v2-local --var SUBMIT_TOKEN:local-submit-token-for-tests --var WORKER_TOKEN:local-worker-token-for-tests --var MANAGER_TOKEN:local-manager-token-for-tests --var VIEWER_TOKEN:local-viewer-token-for-tests
```

Those are deliberately non-production test tokens. The demo app overrides connection settings for its own process only. The local server must be running while reviewing the demo.

## Verification

- All 331 Python tests passed, including the new client/GUI tests.
- TypeScript and generated-binding checks passed.
- The three migrations applied to an isolated local D1 database.
- 24 registry HTTP checks passed: authorization, active/inactive reads, validation, duplicate/retried requests, revisions, and simultaneous conflicting edits.
- The existing job/lease/resubmission API smoke test passed against the same local service.
- The full manager toolbar and dialogs created, edited, and deactivated a project through HTTP; a new manager instance loaded the persisted SQL row.

## Future V2 hosting

1. Obtain explicit approval to provision a separate V2 database and service.
2. Apply V2 migrations to that new database and deploy `defect-farm-api-v2` to that new service.
3. Verify V2 endpoints and point only V2 clients to them. Project entries are created deliberately by a manager, not by tests or migrations.

The migration is additive. Existing clients and job routes continue to work. Reverting the API can leave the unused table in place; no destructive rollback is needed. Existing job IDs such as `S3Bishop` still need an explicit mapping decision before the V2 worker registry is enforced.
