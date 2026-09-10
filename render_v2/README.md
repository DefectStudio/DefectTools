# Render Farm V2 in Defect Tools

Both apps now live in this Git repository: `manager/` contains Manager V2 and
the local V2 dispatcher; `worker/` contains Worker V2 and its EXE build tooling.
Each keeps its own Python source root and settings directory. Use the launchers
so `portable_pipe_tools` resolves to the intended version. The original V1
source and launchers at the repository root remain available.

## Launch from the Defect Tools root

- `run_manager_v2.bat`: Manager V2 GUI.
- `run_worker_v2.bat`: Worker V2 GUI review (farm actions remain disabled).
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

## Checks and packaging

Run `test_render_v2.bat --no-pause` for both Python suites. API checks run with
`npm run check` from `manager/cloudflare/defect-farm-api` after `npm ci`.
Worker EXE tooling remains at `worker/build_worker.bat`; its existing entry point
is the direct-job pilot, not the newer GUI review. Consolidation does not change
rendering behavior or rebuild the EXE.

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
