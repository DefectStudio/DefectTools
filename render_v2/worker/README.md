# Render Worker V2

Worker V2 runs directly from Python through `../../tools/render_worker_v2.bat`.
The EXE distribution and PyInstaller build tooling were retired on September 21.
Keep the Defect Tools directory structure intact. Root `run_worker_v2.bat` and
this directory's `run_worker_v2_gui.bat` forward to the tools launcher.

## Setup

Install Python 3.11 or newer with Tcl/Tk. The batch launcher prefers a worker
`.venv` if present, then `py -3`, then `python`. No pip packages are needed.
Unreal, required plugins, local project assets and Dropbox access must already
be available. Git is not required for the registered-project render workflow.

Launch the worker, select the Dropbox root and UnrealEditor-Cmd.exe, register
local projects with **+**, then use **Check Setup** and **Start Worker**.
Workers claim eligible jobs from the company's separate hosted V2 SQL service.
The included `worker_company_connection.json` supplies only the company worker
credential. There is no operator connection setup or filesystem-queue fallback.

Settings and rotating logs use `%LOCALAPPDATA%/DefectStudio/RenderWorkerV2`,
preserving settings from the old EXE. On GUI launch, old `LocalSaveFiles`
preferences are copied only when the corresponding per-user file is absent.
Machine settings and logs are not distributed with the code.

## Checks

- `test_worker.bat --no-pause`: regression suite, no real render.
- `../../tools/render_worker_v2.bat --self-test REPORT.json`: GUI, registration,
  resources, persistence and external-process smoke test; no SQL jobs or renders.
- The launcher also supports `check-setup`, `render` and `claim-once` diagnostic
  commands. The latter two can perform real renders when explicitly requested.

See [distribution details](docs/portable-worker-v2.md) and
[hosted Bishop acceptance](docs/hosted-bishop-acceptance-20260917.md).
The existing hosted render acceptance used the former EXE; a second-machine
Python/batch render test remains pending.

Automatic project discovery and project preparation belong to the historical
pilot (`run_worker.bat`, `render_project.bat`). They are not the current V2 GUI.
Registered projects are selected manually; the download checkbox defaults off
and downloading is not implemented by this GUI. Neither rendering nor claiming
automatically pulls project repositories. V1 tools remain separate and unchanged.
