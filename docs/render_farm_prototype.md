# Render Farm Filesystem Queue Prototype

This checkpoint proves the smallest useful farm behavior before Unreal, Git sync,
or output validation are connected.

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
- Process one queued job with the current simulation result.
- Display worker and filesystem activity in a live output log.

Filesystem operations run outside the Tk main thread so a slow network share
does not freeze the window. The interface prevents closing while one of these
operations is active. It remembers the last selected base folder in the local,
Git-ignored `LocalSaveFiles/render_worker_local_save.json` file.

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
- Unreal command-line launch
- Movie Render Queue / Movie Render Graph execution
- Frame/output validation
- Worker heartbeats or stalled-job recovery
- Automatic retries

For now, the stick figure can take exactly one carefully supervised step.
