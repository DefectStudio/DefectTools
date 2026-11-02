# Defect Farm Dispatcher

Cloudflare Worker and D1 control plane for Defect's remote Unreal render farm.
The complete render-job JSON, job state, worker leases, blacklists, worker
check-ins, and a bounded final log tail live in D1. Unreal projects and rendered
EXRs/MP4s remain on the existing Dropbox storage.

## Current data flow

1. Unreal submits each complete job JSON directly to the Worker API.
2. D1 is the sole authority for queue order, claims, leases, retries, and final
   state. No Dropbox control package is created.
3. A remote Render Worker claims the full payload over HTTPS and atomically
   materializes it into a private machine-local spool under
   `%LOCALAPPDATA%\DefectStudio\RenderFarm\CloudJobSpool`.
4. Unreal renders to the same worker-local Dropbox show path selected in the
   Render Worker GUI. Large EXRs and MP4s may sync independently without
   delaying job discovery or claims. At the end of each attempt, the worker
   best-effort copies only its small render logs into Dropbox
   `renderFarm/03_RenderComplete` or `renderFarm/04_RenderFailed`; their sync
   state never controls the D1 job.
5. The Farm Render Manager reads and controls jobs and workers through D1.

R2 output delivery is intentionally deferred. Dropbox remains the render-output
transport until that separate migration is approved.

## Local setup

1. Copy `.dev.vars.example` to `.dev.vars` and replace every token.
2. Run `npm install`.
3. Run `npm run types`.
4. Run `npm run migrate:local`.
5. Run `npm run dev`.

Never commit `.dev.vars`, `.env`, or production tokens.

## Production deployment

For Render Worker V2 progress receipts, apply `0004_render_progress.sql` to
the **V2** database before deploying the updated V2 API. Use only the explicit
production configuration:

```powershell
npx wrangler d1 migrations apply defect-farm-v2-production --remote --config wrangler.production.jsonc
npx wrangler deploy --dry-run --config wrangler.production.jsonc --outdir I:\AICache\RenderWorker-Progress-20261101\api-dry-run
npx wrangler deploy --config wrangler.production.jsonc
```

This is an additive nullable column. Existing workers can continue sending only
`progress`; new workers send the latest render counters and phase in
`progress_details` once a minute. The server validates an allowlist, stamps
`received_utc`, and clears live details when the job finishes, is requeued, or
is claimed by a new attempt. `last_progress_age_seconds` measures actual render advancement
at check-in; neither lease renewal nor `updated_utc` indicates frame progress.
Current frame counters describe rendering position, not validated files on disk.
Old APIs ignore the additional heartbeat field and still accept the percentage;
the new API and migration are required to display frame/stage details.

The D1 binding is named `DB` and targets `defect-farm-v2-production` in that
production configuration. Keep `SUBMIT_TOKEN`, `WORKER_TOKEN`, `MANAGER_TOKEN`,
and `VIEWER_TOKEN` as encrypted Worker secrets. This rollout does not rotate
credentials or change V1 resources.
