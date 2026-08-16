# Defect Farm Dispatcher

Cloudflare Worker and D1 control plane for Defect's remote Unreal render farm.
Only job metadata and status travel through Cloudflare. Unreal projects, EXRs,
MP4s, and archived logs remain on the existing Dropbox storage.

## Local setup

1. Copy `.dev.vars.example` to `.dev.vars` and replace every token.
2. Run `npm install`.
3. Run `npm run types`.
4. Run `npm run migrate:local`.
5. Run `npm run dev`.

Never commit `.dev.vars`, `.env`, or production tokens.

## Production deployment

1. Configure `SUBMIT_TOKEN`, `WORKER_TOKEN`, and `MANAGER_TOKEN` as encrypted
   Worker secrets.
2. Run `npm run migrate:remote`.
3. Run `npm run deploy:dry-run`.
4. Run `npm run deploy`.

The D1 binding must be named `DB` and target `defect-farm-production`.
