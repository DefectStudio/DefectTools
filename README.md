# PortablePipeTools

Portable external Python tools for animation pipeline work outside Unreal Engine.

Initial goals:
- Manage show folder creation
- Write show manifests
- Support file-server pipeline workflows
- Eventually integrate with ClickUp, Natron, DaVinci, RV, SyncSketch, and UnrealTools

## Auto Comp - Natron GUI concept

Launch the static Auto Comp interface concept:

```bat
tools\auto_comp_natron.bat
```

The window shows placeholder Show, Sequence, and Shot browsers plus EXR, MP4,
MOV, and Hero output options. EXR, MP4, and Hero default on; MOV defaults off.
When Auto Comp creates a Natron project, those four choices are persisted on the
template's SmartWrite node. On first launch it asks for the shared repository
folder and saves the
choice to `LocalSaveFiles\auto_comp_natron_local_save.json`. The toolbar reports
whether that saved repository is connected, and its Repository button or
**File > Change Repository Folder...** can change the connection later. The
same machine-local file stores the selected Natron executable. Auto Comp prompts
for `Natron.exe` when that setting is missing or invalid; use **File > Change
Natron Executable...** to update it later. The
three browser panels list shows, sequences, and shots from that repository and
remember the last selection between launches. Natron comp creation is not
automatic, but a shot can be right-clicked and **Create Comp** chosen. The tool
copies a sequence-specific `SEQUENCE_000_0000` Natron template when available,
otherwise falls back to `ZZZ_000_0000`, and never overwrites an existing comp.
Multiple shots can be highlighted and processed sequentially from the same
context-menu action. A sequence can also be right-clicked and **Create All
Comps** chosen to process every production shot in that sequence; its special
`SEQUENCE_000_0000` template shot is excluded.
Create Comp results and errors appear in the status bar at the bottom of the
window without interrupting the artist with a pop-up. Batch results report the
number of successful and failed comp creations.

The Shot context menu also provides **Create and Open Comp** and **Open Comp**.
Create and Open uses the normal template fallback when needed, or opens the
existing comp unchanged. Open Comp requires an existing file. Both launch the
`.ntp` file directly in Natron with the source-controlled `natron_plugins`
directory added to `NATRON_PLUGIN_PATH`, ensuring Smart Read is available. Before
Natron launches, both actions find the latest beauty EXR version and download any
Dropbox online-only frames by opening each Windows cloud placeholder. Comp
creation and launch stop if a source download fails. The status bar reports
per-frame download progress and the final download count. An after-load script
then rescans Smart Read nodes once Natron has restored the whole project,
replacing any internal Read paths inherited from the comp template.

Shots also provide **Render Comp**. It requires an existing comp containing at
least one SmartWrite node, hydrates the source sequence, and runs SmartWrite's
Render All behavior asynchronously through `NatronRenderer.exe`. Completion or
failure is reported in Auto Comp's status bar.

## Natron Smart Read PyPlug

The first Smart Read custom-node scaffold lives in `natron_plugins`. Launch
Natron with `tools\natron_with_portable_plugins.bat` so Natron discovers the
source-controlled PyPlug through `NATRON_PLUGIN_PATH`. In Natron's node menu,
the node is listed as `PortablePipeTools > SmartRead`.

Smart Read resolves the shot from the comp's required `SHOT/comp/natron`
location and scans `SHOT/lite/unreal/_output`. Each node has an independent
Element value (such as `beauty` or `environment`) and reads matching
`SHOT_ELEMENT_v###` folders. It selects the highest populated EXR version when
**Latest** is enabled. The always-visible **File** combo lists every discovered
version in ascending order, while **Refresh** rescans the current element on demand.
Choosing an older File version turns Latest off. The selected sequence and frame
range are sent to the internal native Read node without exposing separate path or
frame boxes.

## Natron Smart Write PyPlug

Smart Write lives in `natron_plugins` and is listed as
`PortablePipeTools > SmartWrite`. EXR, MP4, and Hero outputs are enabled by
default; MOV is disabled. The node derives its shot from the comp's
`SHOT/comp/natron` location. It writes versioned beauty outputs under
`comp/_output`. EXR beauty, MP4, and MOV share the next version above the
highest existing `SHOT_beauty_v###` output, while the unversioned Hero EXR
sequence continues to target `comp/_output/_hero` for overwrite. Smart Write
creates any missing parent directories for its enabled outputs when it resolves
the current shot.

Its Smart Write page also provides collapsible EXR, MP4, MOV, and Hero settings
sections. These expose artist-facing controls synchronized to the corresponding
internal writer parameters, such as EXR compression and bit depth or video
codec, FPS, quality, and bitrate. New MP4 writers default to `libx264`.
Pipeline-owned filenames and writer enable controls remain protected.
**Render All** submits every checked output together over the project timeline
range. Each output row also has its own render button; that button is available
when the corresponding output checkbox is enabled.

## Farm Render Manager

Launch the render-farm monitoring interface:

```bat
tools\farm_render_manager.bat
```

The UI provides a project filter, a multi-column render-job list, expandable
Deadline-style details for the selected job, and its current render log in a
compact dark monitor layout.
Click any Jobs column heading to sort by that field; click it again to reverse
the order. The active heading shows the current direction.

On first launch, the manager asks for this computer's Dropbox folder and saves
the choice to `LocalSaveFiles\farm_render_manager_local_save.json`. This file is
machine-local and ignored by Git. Use **File > Change Dropbox Folder...** to
change the connection later.

When connected, the manager scans each project's `renderFarm` folder and all
five queue-state folders. Each job folder becomes a `RenderJob` object, and the
resulting list populates the Jobs panel. Refresh performs the same scan again.
Selecting a job loads its Unreal log into the bottom panel, with captured stdout
and recorded failure details used as fallbacks when the primary log is absent.
The right panel groups the first selected job's metadata into General,
Submission, Render, Worker & Timing, Output, Result, and Advanced sections.
Auto-refresh is enabled by default and scans the connected repository on a
background worker at a selectable 1, 2, 5, or 10 minute interval. The toolbar
checkbox can pause or resume it, and both its state and selected interval are
remembered in the machine-local manager configuration.
Manual refresh shows in-button progress and completion feedback, while the
status bar records the most recent successful update time.
The window and Windows taskbar use the bundled camera emoji icon.
Jobs can be permanently removed through the Jobs panel context menu or Delete
key. Ctrl-click, Shift-click, and Ctrl+A support bulk selection; Edit also
contains Select All and Clear Selection. Every delete route uses the same
default-No confirmation prompt.

The toolbar **Workers** button switches the Jobs panel to a live worker list;
the same button becomes **Jobs** to switch back. Worker rows show their project,
state, current job, last heartbeat, and PortablePipeTools commit. Selecting a
worker displays its heartbeat details and raw status JSON. Right-clicking a
worker and choosing **STOP Worker** creates an empty `WORKERNAME_STOP.json`
marker in that show's `renderFarm\Workers` folder.

The Jobs table displays submitted UTC timestamps in Pacific time using
`YYYY-MM-DD  |  HH:MM`, with PST/PDT selected automatically for the job date.
Its **Render Time** column updates active jobs every second as `HH:MM:SS` and
keeps the final duration visible for completed jobs.

## Render farm worker

The filesystem worker can publish a fake test job, atomically claim one queued
job, simulate completion/failure, or launch UnrealEditor-Cmd for a real Movie
Render Graph job published by the Unreal rendering tool.

Launch the Render Worker interface:

```bat
tools\render_worker_gui.bat
```

At startup, the GUI verifies the PortablePipeTools repository itself before it
enables any worker controls. It requires a clean checkout and runs
`git pull --ff-only` on the current upstream branch. When an update changes the
checked-out commit, the GUI exits and the BAT launcher immediately restarts it
using the newly pulled code. An update failure leaves job processing disabled,
so an outdated worker cannot claim a farm job.

Choose the show-specific `RenderFarm` base folder in the interface. The window
can initialize the five queue folders, create a fake job, simulate one job, or
render one real job with Unreal while displaying activity in its output log.
**Start Worker** keeps listening for real jobs at a configurable interval
(15 seconds by default); **Stop Worker** interrupts an already-claimed Unreal
render, requeues it as a failed attempt, and stops before claiming another.
**Give Up On Render Timer** limits each Unreal process to 2 hours by default.
When the timer expires, the worker stops Unreal, requeues the timed-out attempt,
and remains available to process another eligible job.

While automatic listening is active, the worker publishes
`Workers\WORKERNAME_STATUS.json` every 10 seconds. It includes the worker state,
session, current shot/version/render setting, and tools Git commit. A heartbeat
older than 45 seconds is shown as stale. Empty `WORKERNAME_STOP.json` files are
existence-only stop commands: waiting workers stop immediately, while active
Unreal renders check every half-second, interrupt the process, requeue the job,
and stop. Both files are removed after a clean stop.

Before every real job, the worker verifies that the selected Unreal checkout is
clean and runs `git pull --ff-only` on its current upstream branch. The latest
pulled commit is rendered even when it is newer than the job's submitted
commit. If Git cannot update safely, the job remains in `01_NeedsRendering`
instead of being claimed and failed.

Each render computer can select its own **Local Unreal Project (.uproject)**.
That machine-local path overrides the absolute project path recorded by the
submitting computer, so workers may use different drive letters and checkout
locations. The worker derives its local show root from the selected **Show
Render Farm Base Folder**: the parent of the required `renderFarm` folder is the
show root. Real renders use that computer-local root, so Dropbox may use a
different drive letter on every worker without any worker-side INI file.

Before Unreal starts, the worker checks the local MP4 and EXR version targets.
If output already exists, the job is failed safely with instructions to submit a
new render version instead of silently overwriting an earlier render.

When a valid render attempt fails, the worker appends its normalized name to the
job's `blacklisted_workers` array, resets the job to `queued`, and atomically
returns its package to `01_NeedsRendering`. That worker ignores the job on later
queue scans, while another worker can claim and retry it. Each additional failed
worker is added to the same list. Corrupt or unreadable job metadata still moves
to `04_RenderFailed` because it cannot safely participate in automatic retries.

The interface also displays transparent pixel-art animations for the worker's
Stopped, Waiting, Moving Files, Rendering, and Finishing stages. The five
sheets are loaded automatically from the repository's `spriteImages` folder. Source
frames are 48x48 and are displayed at a crisp 2x scale. While a job is active,
the activity panel shows its shot, version, and render setting. Every entered
worker stage remains visible for at least five seconds.

Command-line walking test:

```bat
tools\create_test_render_job.bat D:\RenderFarmPrototype
tools\render_worker.bat D:\RenderFarmPrototype --worker-name RENDER-03 --simulate-result success
```

One supervised real job:

```bat
tools\render_worker.bat "F:\Defect Dropbox\defect\s3bishop\renderFarm" --worker-name RENDER-03 --render-with-unreal --local-uproject "D:\UnrealProjects\s3bishop\s3bishop.uproject" --unreal-editor-cmd "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

See [docs/render_farm_prototype.md](docs/render_farm_prototype.md) for the queue
contract, real-render behavior, manual failure test, and deferred features.
