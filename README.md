# PortablePipeTools

Portable external Python tools for animation pipeline work outside Unreal Engine.

Initial goals:
- Manage show folder creation
- Write show manifests
- Support file-server pipeline workflows
- Eventually integrate with ClickUp, Natron, DaVinci, RV, SyncSketch, and UnrealTools

## Render farm worker

The filesystem worker can publish a fake test job, atomically claim one queued
job, simulate completion/failure, or launch UnrealEditor-Cmd for a real Movie
Render Graph job published by the Unreal rendering tool.

Launch the Render Worker interface:

```bat
tools\render_worker_gui.bat
```

Choose the show-specific `RenderFarm` base folder in the interface. The window
can initialize the five queue folders, create a fake job, simulate one job, or
render one real job with Unreal while displaying activity in its output log.
**Start Worker** keeps listening for real jobs at a configurable interval
(15 seconds by default); **Stop Worker** finishes an already-claimed render and
stops before claiming another.

The interface also displays transparent pixel-art animations for the worker's
Waiting, Moving Files, Rendering, and Finishing stages. The four sheets are
loaded automatically from the repository's `spriteImages` folder. Source
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
tools\render_worker.bat "F:\Defect Dropbox\defect\s3bishop\renderFarm" --worker-name RENDER-03 --render-with-unreal --unreal-editor-cmd "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
```

See [docs/render_farm_prototype.md](docs/render_farm_prototype.md) for the queue
contract, real-render behavior, manual failure test, and deferred features.
