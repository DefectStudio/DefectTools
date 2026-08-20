# Render Farm Filesystem Worker

> **Legacy reference:** this document describes the original Dropbox
> filesystem-queue prototype. Production Cloud mode now stores complete job
> payloads, leases, state, blacklists, and worker controls in Cloudflare D1.
> Workers materialize claims into a private local spool and use Dropbox only for
> the final EXR/MP4 output paths. See `cloudflare/defect-farm-api/README.md` for
> the current data flow.

This checkpoint supports supervised and continuous filesystem-queue processing,
including real Unreal 5.8 Movie Render Graph launches and post-render output
validation, worker heartbeats, and filesystem-based remote stopping.

## Queue folders

The worker creates these folders beneath the supplied farm root:

```text
00_Submitting
01_NeedsRendering
02_IsRendering
03_RenderComplete
04_RenderFailed
Workers
```

`00_Submitting` is never scanned by workers. A submission becomes visible only
when its complete job folder is renamed into `01_NeedsRendering`.
`Workers` is not a job queue; it contains live worker heartbeat and remote STOP
marker files.

## Render Worker interface

Launch the Tkinter interface from the repository root:

```bat
tools\render_worker_gui.bat
```

The BAT launcher supplies its parent directory as the PortablePipeTools Git
root and supervises automatic restarts. Before worker controls are enabled, the
GUI requires that checkout to be clean and runs `git pull --ff-only` on its
current upstream branch. If the pull changes the commit, the GUI exits with the
dedicated restart code `75`; the BAT immediately relaunches the updated worker.
If the repository is dirty, detached, missing an upstream, offline, or cannot
fast-forward, the GUI reports the reason and leaves all job-processing controls
disabled. This check occurs before the worker can listen to or claim a job.

Use **Show Render Farm Base Folder** to select the show-specific `RenderFarm`
folder that directly contains the five queue folders. The interface can:

- Initialize or validate the queue folders.
- Publish a fake test job.
- Simulate one queued job with the selected test result.
- Claim and render one real queued job with UnrealEditor-Cmd.
- Continuously listen for and process real jobs until stopped.
- Display worker and filesystem activity in a live output log.

The **UnrealEditor-Cmd.exe** field is remembered in the same machine-local
settings file as the farm folder. **Render One Job with Unreal** shows a
confirmation before it claims anything. **Simulate One Job** remains a separate
safe path for fake jobs and queue testing.

The **Local Unreal Project (.uproject)** field is also machine-local. The GUI
requires it for real renders, and it overrides the absolute `uproject` path
stored by the submitting computer.
The selected filename must match the farm job's `project` name, ignoring case.
This allows render workers to use different drive letters and checkout roots
without changing the immutable submission record.

The worker derives the machine-local show root from the selected **Show Render
Farm Base Folder**. That folder must be named `renderFarm`; its parent is treated
as the show root and reported in the confirmation and worker log. The worker
combines that root with the job's portable `output_relative_directory`. For
example, an artist may
submit an `F:` output while another worker renders to the matching `I:` Dropbox
location. No `QuickWidgetToolsSettings.ini` is required by the worker.

Completed and failed manifests preserve `submitted_output_directory` and add
`worker_show_file_server_path`, `worker_output_directory`, and `worker_uproject`
for diagnostics. Before Unreal launches, the worker checks the destination MP4
and EXR version folder. Existing output stops the render safely and asks for a
new render version, preventing accidental overwrite.

After Movie Render Graph finishes, the Unreal executor collects files from MRG
`graph_data` and validates them on disk before reporting success. An enabled MP4
must exist, and an enabled EXR output must contain at least the job's expected
frame count. Validation details and the final file count are preserved in
`unreal_result.json`, `result.json`, and the terminal job manifest. Missing
outputs count as a failed attempt even if Unreal's pipeline callback reported
success; the worker blacklists itself from that job and returns the package to
`01_NeedsRendering` for another worker.

**Start Worker** begins continuous real-job processing. The polling interval is
configurable from 1 to 3600 seconds and defaults to 15 seconds. When the queue is
empty, the bottom status counts down to the next check, for example:

```text
Waiting for jobs — next check in 12 seconds
```

**Give Up On Render Timer** limits each Unreal process from 0.25 to 24 hours and
defaults to 2 hours. A timed-out Unreal process is terminated, the failed attempt
is requeued and blacklists that worker from the job, and the automatic worker
immediately checks for another eligible job. The saved timer also applies to
**Render One Job with Unreal**.

Only one automatic listener can exist in a GUI instance, and the supervised
buttons and worker configuration are locked while it is active. After a job
completes or is requeued following a failed attempt, the listener immediately
checks for another. The failed job is ignored because it now blacklists that
worker. After an empty eligible queue or unexpected worker error, the listener
waits for the configured interval and then continues listening.

## Failed-attempt blacklist and retry protocol

A valid job that fails to render is not moved to `04_RenderFailed`. Before the
claimed package is returned to `01_NeedsRendering`, its `job.json` is reset to
`status: queued` and the worker's normalized name is appended to the
`blacklisted_workers` array. The failed attempt remains available in
`last_failure` and `result.json`, and `attempt` remains incremented.

Workers filter the queue using `blacklisted_workers` before Git preflight and
again before the atomic claim. Matching is case-insensitive. A blacklisted
worker ignores the package, but any worker not in the list can claim it. If that
worker also fails, its name is appended and the same package is requeued again.
A successful worker moves it normally to `03_RenderComplete` with the accumulated
blacklist retained for diagnostics. Invalid or unreadable `job.json` packages
still move to `04_RenderFailed` so malformed jobs cannot circulate forever.

**Stop Worker** is immediate for an active Unreal render. If no job has been
claimed, the current queue check stops before claiming one. If a render is
already claimed, the worker terminates Unreal, records the interruption as a
failed attempt, returns the job to `01_NeedsRendering`, and then stops. The
interrupted worker is blacklisted from that job, and any partial render output is
preserved for manual inspection or cleanup.

## Worker heartbeat and remote STOP protocol

Starting the automatic worker publishes
`Workers\WORKERNAME_STATUS.json` immediately and updates it every 10 seconds.
The JSON includes the worker and machine names, a unique session ID, process ID,
activity state, current job fields, PortablePipeTools branch and commit, and UTC
heartbeat timestamps. A fresh status file with the same worker name blocks a
second listener session. Heartbeats older than 45 seconds are treated as stale,
allowing a crashed or disconnected machine to remain visible without appearing
online.

`Workers\WORKERNAME_STOP.json` is an existence-only command and may be a
completely empty, zero-byte file. A waiting worker checks for it during every
heartbeat; an active Unreal render checks every half-second. A waiting worker
stops before claiming another job, while a rendering worker interrupts Unreal,
requeues the job as a failed attempt, and stops. The status changes to
`stopping_after_current_job` while the interrupted attempt is finalized. After
a clean stop, the worker removes both its status and STOP files. A marker created
while the worker is offline remains pending and prevents its next startup.

Farm Render Manager's **Workers** toolbar button toggles the left panel between
Jobs and Workers. The Workers view shows project, status, current job, last seen,
and tools commit; the right panel shows worker details and the bottom panel shows
the raw heartbeat JSON. Right-click **STOP Worker** creates the empty marker.

The animation sheets are loaded automatically from the repository-level
`spriteImages` folder:

```text
Base_Idle.png          Waiting to find a job
Base_Run.png           Moving files and claiming the job
Base_WateringCan.png   Rendering
Base_Hoe.png           Finishing render tasks
```

Each sheet is one row of transparent 48x48 PNG frames. The GUI slices the sheets
at runtime and displays them with pixel-preserving 2x integer scaling. The stage
name is always shown directly beneath the animation. Once a job is claimed, a
second line shows the active shot, zero-padded version, and short render-setting
name until the job reaches Render Complete or is requeued after a failed attempt.

The default minimum stage duration is five seconds. This timer surrounds the
real stage operation: a fast simulated action remains visible for five seconds,
while a slow Dropbox or Unreal operation naturally stays in that stage for its
actual longer duration. A successful simulated job therefore displays
Waiting, Moving, Rendering, and Finishing for at least 20 seconds total.

Filesystem operations run outside the Tk main thread so a slow network share
does not freeze the window. The interface prevents closing while one of these
operations is active. It remembers the last selected base folder in the local,
Git-ignored `LocalSaveFiles/render_worker_local_save.json` file. The selected
Unreal executable is remembered in the same machine-local settings file.

## One supervised real Unreal render

Publish jobs from `WBP_03_RenderingTool` first. A real job must contain the
submitting project's `.uproject` path and identity, level, level sequence, Movie
Render Graph preset, and serialized graph-variable overrides. A worker-local
project selection may override that submitted path. The worker rejects fake test
jobs in real-render mode.

For the current `s3bishop` worker, launch the GUI:

```bat
tools\render_worker_gui.bat
```

Then:

1. Select `F:\Defect Dropbox\defect\s3bishop\renderFarm`.
2. Select `C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe`.
3. Select this computer's local `s3bishop.uproject` and verify that the derived
   show path is the parent of the selected `renderFarm` folder.
4. Click **Render One Job with Unreal** and accept the confirmation.
5. Watch the Rendering stage and live output log.

Once a supervised job succeeds, use **Start Worker** for continuous processing
and **Stop Worker** when the computer should stop accepting new work.

The command-line equivalent is:

```bat
tools\render_worker.bat "F:\Defect Dropbox\defect\s3bishop\renderFarm" --worker-name RENDER-03 --render-with-unreal --local-uproject "D:\UnrealProjects\s3bishop\s3bishop.uproject" --unreal-editor-cmd "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

The worker claims at most one job. It launches Unreal in `-game`, unattended,
offscreen mode, creates an MRQ job from the published snapshot, assigns the Movie
Render Graph, reapplies the exact serialized overrides, and waits for an explicit
Unreal completion result. The default process timeout is 2 hours. The
command-line worker also watches its `Workers\WORKERNAME_STOP.json` marker while
Unreal runs, interrupts the process when requested, and consumes the marker
before exiting.

The claimed/final job folder records:

```text
render_command.txt    Exact command used for diagnosis
git_pull.log          Git commands and output from the successful pre-job pull
unreal.log            Unreal's normal absolute log
unreal_stdout.log     Captured process output
unreal_result.json    Explicit executor success/failure and reported outputs
result.json           Farm terminal state written by the external worker
```

An exit code of zero is not sufficient on its own. The job completes only when
Unreal also writes a matching, successful `unreal_result.json`; otherwise the
worker is added to `blacklisted_workers` and the job is requeued with the
diagnostic files kept beside it for the next worker.

Before claiming each real job, the worker requires a clean checkout, verifies
that the current branch has an upstream, and runs `git pull --ff-only`. It then
requires the local branch to exactly match that upstream. The latest pulled
commit is rendered regardless of the job's `submitted_git_commit` value.

A successful pull is recorded in `git_pull.log` and in the job's `git_*`
fields, with `worker_sync_policy: latest_branch_git_pull_ff_only`. If this
preflight fails, the job remains in `01_NeedsRendering`; the automatic worker
waits for its next polling interval before trying again.

## Manual walking test

From the repository root:

```bat
tools\create_test_render_job.bat D:\RenderFarmPrototype
tools\render_worker.bat D:\RenderFarmPrototype --worker-name RENDER-03 --simulate-result success
```

To test the failed-attempt retry path:

```bat
tools\create_test_render_job.bat D:\RenderFarmPrototype
tools\render_worker.bat D:\RenderFarmPrototype --worker-name RENDER-03 --simulate-result failure
```

The worker processes at most one eligible job and exits. A failed simulation
returns the package to `01_NeedsRendering` and blacklists `RENDER-03` from it.
Running the same command again ignores that package; using a different worker
name claims it. An empty eligible queue is a successful no-op. Higher numeric
priorities render first; equal priorities use the oldest `submitted_utc` first.

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

Dropbox can change a directory rename's error from a sharing violation to
`WinError 5` while it finishes observing the folder. Directory renames therefore
also retry error 5 for the same bounded 15-second window. Other file reads and
writes still treat access denied as a real permission failure immediately.

## Deliberately not in this checkpoint

- A Windows service
- Git or Git LFS synchronization
- Stalled-job recovery
- Cross-machine retry limits or escalation after every known worker is blacklisted

The pixel worker can now take supervised single steps or continuously process
one real job at a time. Stalled-job recovery remains the next unattended-operation
safety checkpoint.
