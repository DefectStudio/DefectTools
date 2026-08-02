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

```bat
tools\create_test_render_job.bat D:\RenderFarmPrototype
tools\render_worker.bat D:\RenderFarmPrototype --worker-name RENDER-03 --simulate-result success
```

See [docs/render_farm_prototype.md](docs/render_farm_prototype.md) for the queue
contract, manual failure test, and intentionally deferred features.
