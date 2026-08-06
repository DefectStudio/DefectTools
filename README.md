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

The window shows placeholder Show, Sequence, and Shot browsers plus Hero and EXR
options. On first launch it asks for the shared repository folder and saves the
choice to `LocalSaveFiles\auto_comp_natron_local_save.json`. The toolbar reports
whether that saved repository is connected, and its Repository button or
**File > Change Repository Folder...** can change the connection later. The
three browser panels list shows, sequences, and shots from that repository and
remember the last selection between launches. Natron comp creation is not
implemented yet.

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
(15 seconds by default); **Stop Worker** finishes an already-claimed render and
stops before claiming another.

While automatic listening is active, the worker publishes
`Workers\WORKERNAME_STATUS.json` every 10 seconds. It includes the worker state,
session, current shot/version/render setting, and tools Git commit. A heartbeat
older than 45 seconds is shown as stale. Empty `WORKERNAME_STOP.json` files are
existence-only graceful-stop commands: waiting workers stop immediately, while
active workers finish their current job and stop before claiming another. Both
files are removed after a clean stop.

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
