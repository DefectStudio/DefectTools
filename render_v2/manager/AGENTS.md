# Render Farm Manager V2

- The user consolidated both V2 apps into Defect Tools on September 10. This is the V2 manager and dispatcher source root inside that repository. See `../README.md`.
- Repository-root `src`, `tools`, and `cloudflare` contain V1. Keep V2 code here and never deploy it to V1 production resources.
- Worker V2 is in sibling `../worker`. The old standalone repositories are historical copies.
- Use the local V2 dispatcher on port 8795 and its own SQL storage under `LocalSaveFiles/v2-backend`. Its database ID is a local placeholder. Any future hosted V2 service needs newly provisioned resources, never V1's IDs.
- V2 clients reject the known V1 production dispatcher URL. Never copy V1 credentials or local configuration into this repository.
- V1 and V2 must remain separately launchable during transition; do not change V1 job state or project IDs.
- Run Python tests with `PYTHONPATH=src`, and API checks/tests from `cloudflare/defect-farm-api`. Use context-mode to process large outputs.
