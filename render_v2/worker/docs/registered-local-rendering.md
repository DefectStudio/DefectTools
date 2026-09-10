# Render a registered local project

Run `run_worker_v2.bat` from the Defect Tools root. Add a Dropbox show and its
local `.uproject`, choose the worker's UnrealEditor-Cmd.exe, then select the
project in the list and click **Render job file…**. Choose a Movie Render Graph
`job.json` for that same show. The job supplies the shot's map, sequence, graph,
frame metadata, and graph variable overrides; no Bishop-specific template is
embedded in the rendering code.

The saved project registration supplies the local `.uproject` and Dropbox path.
An unknown project, mismatched job ID, missing project/engine/farm folder, or
invalid job is rejected. The registration's ID must match its Dropbox show
folder. The renderer uses the local files as they currently exist, including
local edits. It does not search for other checkouts, clone, fetch, pull, switch
branches, or load a remote catalog. This local action performs no project Git
updates regardless of the download checkbox. Optional download provisioning is
separate work.

The worker installs/updates its small managed RenderWorkerRuntime plugin in the
selected project's Plugins folder. It refuses to overwrite an unmanaged plugin.
For Git projects it excludes this worker-owned plugin locally; projects copied
without Git are supported. A per-project lock prevents two workers using that
same local checkout concurrently. Project assets and the `.uproject` are not
edited by this operation.

Each run writes a new folder beneath the registered show's
`WorkerV2Renders/<project>/<shot>/<timestamp-and-id>`. It contains `job/job.json`,
Unreal logs, output files, and `result.json`. The input job and live queue are
unchanged. **Stop Worker** cancels this local render; closing while rendering
requests cancellation and waits for the background operation to finish. Project
editing is locked during rendering.

For command-line use, run `render_v2/worker/render_registered_job.bat` with
`--project <Dropbox-show> --job <job.json>`. Optional arguments include
`--settings`, `--output-root`, and `--timeout` (seconds). The GUI and CLI use the
same registration validation and rendering function.

## Bishop validation — September 10, 2026

- Registration: `s3bishop`, `F:/Projects/s3bishop.uproject`, downloads **off**.
- Engine: `D:/Unreal Engine/5.8/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe`.
- Shot: `ZZZ_000_0850`, using the previously validated shot job metadata. Its old
  pilot catalog ID `bishop` was changed to Dropbox ID `s3bishop` in a new local
  test-job copy; the original job file was preserved.
- First attempt exposed a missing per-run renderFarm directory. Fixed and
  covered by an output-mapping regression check before retrying.
- Successful run: `20260910T193656Z_d6e8ef05`; Unreal exited 0 and the worker
  validated **40 EXRs**, with no output-validation errors.
- Output root: `F:/Defect DropBox2/Defect Dropbox/defect/s3bishop/WorkerV2Renders/s3bishop/ZZZ_000_0850/20260910T193656Z_d6e8ef05`.
- Repeat through the GUI using the saved Bishop registration and
  `render_v2/worker/LocalSaveFiles/bishop_ZZZ_000_0850.local.json` on this machine.
  Each repeat creates a new output directory.

The real render exercised the shared renderer through the CLI. Tk tests cover
the GUI's selection, background completion, Stop callback, and edit locking.
Tests also cover non-Git copies, no Git required, registration rejection,
output isolation, project locks, and failure receipts.

Automatic cloud job assignment, service startup/recovery, and packaging this
updated GUI into the EXE remain separate milestones. The older direct-project
pilot CLI/EXE still has its previous provisioning behavior. Use the registered
GUI or `render_registered_job.bat` for this local-only workflow.
