# PortablePipeTools

Portable external Python tools for animation pipeline work outside Unreal Engine.

Initial goals:
- Manage show folder creation
- Write show manifests
- Support file-server pipeline workflows
- Eventually integrate with ClickUp, Natron, DaVinci, RV, SyncSketch, and UnrealTools

## Render farm queue prototype

The first filesystem render-queue checkpoint can publish a fake job, atomically
claim it by moving its folder, and simulate either completion or failure:

Launch the Render Worker interface:

```bat
tools\render_worker_gui.bat
```

Choose the show-specific `RenderFarm` base folder in the interface. The window
can initialize the five queue folders, create a fake job, process one job, and
display worker activity in its output log.

The interface also displays transparent pixel-art animations for the worker's
Waiting, Moving Files, Rendering, and Finishing stages. Choose the folder that
contains `Base_Idle.png`, `Base_Run.png`, `Base_WateringCan.png`, and
`Base_Hoe.png`. Source frames are 48x48 and are displayed at a crisp 2x scale.
Every entered worker stage remains visible for at least five seconds.

Command-line walking test:

```bat
tools\create_test_render_job.bat D:\RenderFarmPrototype
tools\render_worker.bat D:\RenderFarmPrototype --worker-name RENDER-03 --simulate-result success
```

See [docs/render_farm_prototype.md](docs/render_farm_prototype.md) for the queue
contract, manual failure test, and intentionally deferred features.
