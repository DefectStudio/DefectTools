# Render Farm V2 in Defect Tools

Both apps now live in this Git repository: `manager/` contains Manager V2 and
the V2 dispatcher; `worker/` contains Worker V2 Python source and resources.
Each keeps its own Python source root and settings directory. Use the launchers
so `portable_pipe_tools` resolves to the intended version. The original V1
source and launchers at the repository root remain available.

## Launch from the Defect Tools root

- `run_manager_v2.bat`: Manager V2 GUI.
- `run_worker_v2.bat`: Worker V2 GUI with registered local rendering.
- `tools/render_worker_v2.bat`: primary Worker V2 launcher; runs Python source directly.
- `run_v2_backend.bat`: isolated local V2 dispatcher on port 8795.

Python 3.11 or newer with Tk is required for the source GUIs. Install Node.js for
the backend; its root launcher runs `npm ci` when dependencies are missing.
Migrations apply only to the local V2 database. Stop any other local V2
dispatcher using port 8795 before starting it.

Configure the Dropbox root in each GUI. Exact immediate show folder names with
a `renderFarm` child supply the project list. Register the worker's local Unreal
project path manually; project downloads stay off by default.

V1 production resources and credentials are not shared with V2. Machine settings,
local databases, virtual environments, build outputs, and downloaded projects
were not imported. Reconfigure preferences for these new app locations.

## Checks and distribution

Run `test_render_v2.bat --no-pause` for both Python suites. API checks run with
`npm run check` from `manager/cloudflare/defect-farm-api` after `npm ci`.
Worker V2 is distributed as Python source with `tools/render_worker_v2.bat`.
Install Python 3.11+ with Tcl/Tk on each worker; no pip dependencies are required.
Keep the Defect Tools directory structure intact when copying or updating it.
The company worker-only connection ships in `worker/worker_company_connection.json`;
operators do not provision credentials. The EXE and PyInstaller build scripts
were retired on September 21. Settings and logs retain the former EXE's location:
`%LOCALAPPDATA%/DefectStudio/RenderWorkerV2`. Machine configuration, temporary
validation files, and old build outputs remain ignored.

**Latest worker milestone:** [Registered queue claiming](worker/docs/registered-queue-claiming.md)
connects Start Worker to eligible jobs in the separate hosted V2 SQL service.
There is no filesystem-claim fallback. Bishop ZZZ_000_0850 passed the full hosted
submission/claim/render/completion path with the packaged EXE on September 17;
see [acceptance evidence](worker/docs/hosted-bishop-acceptance-20260917.md).

Consolidation validation: 320 manager tests and 175 worker tests passed through
the combined root launcher. The copied V2 dispatcher's type checks also passed.

## Import record

Imported committed sources from Manager `782283a` and Worker `8893bc0` on
September 10, 2026. The old local repositories at `F:/RenderFarmManager` and
`F:/RenderWorker` remain historical copies; continue development here.
The manager copy omits unrelated diagnostic snapshots and old installation
artifacts. Historical documents mentioning separate repositories are superseded
by this file. There are no nested Git repositories or submodules. Both apps
travel with the normal Defect Tools push.
