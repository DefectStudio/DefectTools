# Render Farm Manager V2

- The user consolidated both V2 apps into Defect Tools on September 10. This is the V2 manager and dispatcher source root inside that repository. See `../README.md`.
- Repository-root `src`, `tools`, and `cloudflare` contain V1. Keep V2 code here and never deploy it to V1 production resources.
- Worker V2 is in sibling `../worker`. The old standalone repositories are historical copies.
- The company manager entrypoint is `../../tools/run_manager_v2.bat`; existing root/source launchers are aliases. Keep startup failures visible and logged. Per-user settings/logs live in `%LOCALAPPDATA%/DefectStudio/RenderFarmManagerV2`. The private manager profile remains in `%LOCALAPPDATA%/DefectStudio/RenderFarmV2/company-manager.json`; do not substitute worker/submitter credentials or include manager credentials in the shared checkout. `--self-test REPORT` checks hosted read access and the real GUI without mutating jobs.
- The user approved and deployed hosted V2 on September 15: `defect-farm-api-v2.twilight-tooth-7b7c.workers.dev`, database `defect-farm-v2-production` (`2d3669f5-5114-4a50-9a9c-69463f9e7b48`). Use `wrangler.production.jsonc` only for that separate V2 service. The normal manager launcher uses the private company-manager profile. `run_manager_v2_local.bat`, port 8795 and `wrangler.jsonc` retain local development with the placeholder database ID. Never use V1 IDs or credentials.
- V2 clients reject the known V1 production dispatcher URL. Never copy V1 credentials or local configuration into this repository.
- V1 and V2 must remain separately launchable during transition; do not change V1 job state or project IDs.
- Run Python tests with `PYTHONPATH=src`, and API checks/tests from `cloudflare/defect-farm-api`. Use context-mode to process large outputs.
