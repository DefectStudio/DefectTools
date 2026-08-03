# Render Farm Filesystem Worker

This checkpoint supports one supervised filesystem-queue step, including a real
Unreal 5.8 Movie Render Graph launch. Git synchronization, continuous polling,
and frame/output validation remain separate checkpoints.

## Queue folders

The worker creates these folders beneath the supplied farm root:

```text
00_Submitting
01_NeedsRendering
02_IsRendering
03_RenderComplete
04_RenderFailed
```

`00_Submitting` is never scanned by workers. A submission becomes visible only
when its complete job folder is renamed into `01_NeedsRendering`.

## Render Worker interface

Launch the Tkinter interface from the repository root:

```bat
tools\render_worker_gui.bat
```

Use **Show Render Farm Base Folder** to select the show-specific `RenderFarm`
folder that directly contains the five queue folders. The interface can:

- Initialize or validate the queue folders.
- Publish a fake test job.
- Simulate one queued job with the selected test result.
- Claim and render one real queued job with UnrealEditor-Cmd.
- Display worker and filesystem activity in a live output log.

The **UnrealEditor-Cmd.exe** field is remembered in the same machine-local
settings file as the farm and sprite folders. **Render One Job with Unreal**
shows a confirmation before it claims anything. **Simulate One Job** remains a
separate safe path for fake jobs and queue testing.

The **Animation Sprite Folder** selects a local folder containing these paid
production assets, which are intentionally not copied into this repository:

```text
Base_Idle.png          Waiting to find a job
Base_Run.png           Moving files and claiming the job
Base_WateringCan.png   Rendering
Base_Hoe.png           Finishing render tasks
```

Each sheet is one row of transparent 48x48 PNG frames. The GUI slices the sheets
at runtime and displays them with pixel-preserving 2x integer scaling. The stage
name is always shown directly beneath the animation.

The default minimum stage duration is five seconds. This timer surrounds the
real stage operation: a fast simulated action remains visible for five seconds,
while a slow Dropbox or Unreal operation naturally stays in that stage for its
actual longer duration. A successful simulated job therefore displays
Waiting, Moving, Rendering, and Finishing for at least 20 seconds total.

Filesystem operations run outside the Tk main thread so a slow network share
does not freeze the window. The interface prevents closing while one of these
operations is active. It remembers the last selected base folder in the local,
Git-ignored `LocalSaveFiles/render_worker_local_save.json` file. The selected
animation sprite folder and Unreal executable are remembered in the same
machine-local settings file.

## One supervised real Unreal render

Publish jobs from `WBP_03_RenderingTool` first. A real job must contain the local
`.uproject` path, level, level sequence, Movie Render Graph preset, and serialized
graph-variable overrides. The worker rejects fake test jobs in real-render mode.

For the current `s3bishop` worker, launch the GUI:

```bat
tools\render_worker_gui.bat
```

Then:

1. Select `F:\Defect Dropbox\defect\s3bishop\renderFarm`.
2. Select `C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe`.
3. Click **Render One Job with Unreal** and accept the confirmation.
4. Watch the Rendering stage and live output log.

The command-line equivalent is:

```bat
tools\render_worker.bat "F:\Defect Dropbox\defect\s3bishop\renderFarm" --worker-name RENDER-03 --render-with-unreal --unreal-editor-cmd "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

The worker claims at most one job. It launches Unreal in `-game`, unattended,
offscreen mode, creates an MRQ job from the published snapshot, assigns the Movie
Render Graph, reapplies the exact serialized overrides, and waits for an explicit
Unreal completion result. The default process timeout is 24 hours.

The claimed/final job folder records:

```text
render_command.txt    Exact command used for diagnosis
unreal.log            Unreal's normal absolute log
unreal_stdout.log     Captured process output
unreal_result.json    Explicit executor success/failure and reported outputs
result.json           Farm terminal state written by the external worker
```

An exit code of zero is not sufficient on its own. The job completes only when
Unreal also writes a matching, successful `unreal_result.json`; otherwise it is
moved to `04_RenderFailed` with the diagnostic files kept beside it.

This checkpoint intentionally renders the worker computer's current project
checkout. It records `rendered_git_commit` and
`worker_sync_policy: current_checkout` in `job.json`, but it does not reset,
clean, pull, or otherwise change the artist's checkout.

## Manual walking test

From the repository root:

```bat
tools\create_test_render_job.bat D:\RenderFarmPrototype
tools\render_worker.bat D:\RenderFarmPrototype --worker-name RENDER-03 --simulate-result success
```

To test the failed path:

```bat
tools\create_test_render_job.bat D:\RenderFarmPrototype
tools\render_worker.bat D:\RenderFarmPrototype --worker-name RENDER-03 --simulate-result failure
```

The worker processes at most one job and exits. An empty queue is a successful
no-op. Higher numeric priorities render first; equal priorities use the oldest
`submitted_utc` first.

## Claim behavior

A claim is a direct directory rename from `01_NeedsRendering` to
`02_IsRendering`, with `__WORKER-NAME` appended. No copy/delete fallback is used.
When two workers race, only the worker whose rename succeeds owns the job.

This assumes all queue folders are on the same filesystem/share. Atomic rename
semantics must still be verified on the studio file server before production use.

JSON updates are written to a temporary file beside `job.json` and published with
`os.replace` so a process interruption is less likely to leave partial JSON.

Dropbox, antivirus software, and other filesystem observers can briefly hold a
new file or folder open on Windows. Every render-farm filesystem stage uses the
same 15-second policy for Windows sharing and lock violations (`WinError 32` and
`33`), including queue initialization and scans, JSON reads and writes, temporary
file cleanup, job publication, worker claims, and terminal-state moves. State
transitions remain direct atomic rename/replace operations; there is no
copy/delete fallback. Other permission errors fail immediately.

## Deliberately not in this checkpoint

- Continuous polling or a Windows service
- Git or Git LFS synchronization
- Frame/output validation
- Worker heartbeats or stalled-job recovery
- Automatic retries

For now, the pixel worker can take exactly one carefully supervised real step.
