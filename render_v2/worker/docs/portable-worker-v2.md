# Portable Render Worker V2

Preview 2.0.0-preview.1, Windows x64. This build packages the current registered-project GUI, its Python/Tk runtime, animation assets and minimal Unreal runtime plugin. The default build no longer launches the older catalog/pilot interface.

See [validation evidence and remaining acceptance tests](portable-worker-v2-validation.md).

## Copy and start

Copy `RenderWorkerV2.exe` to a folder on the target computer and double-click it. Python, Git, pip and a Defect Tools checkout are not required for the registered-local-project workflow. Unreal and the required project assets/plugins must already be available. Run as the intended Windows user; the application does not request administrator elevation.

1. Select the Dropbox root containing your shows using its **Browse** button. Until a root is set, the compact setup screen hides the project list and worker controls. Choosing a folder reveals the full interface immediately; an existing saved root opens the full interface at startup.
2. Confirm the UnrealEditor-Cmd.exe field, then add each project with **+**, select its Dropbox show name, and browse to its local `.uproject`. Installed UE 5.8 is checked once on first use; browse manually if blank or incorrect.
3. For cloud mode, use **Configure Connection…** to save the V2 URL and worker token supplied by the administrator. The URL is blank on a fresh setup; do not distribute the developer's localhost endpoint or credentials. For shared filesystem queues, leave **Use Cloud Dispatcher** unchecked.
4. Click **Check Setup**. It checks local paths, basic write access, available engine-version metadata, disk-space warnings, managed plugin conflicts and worker authentication when cloud mode is selected. It never claims a job or installs a plugin. Full asset/GPU compatibility is verified by an actual render.
5. Click **Start Worker** to begin claiming, or select a registration and use **Render job file…** for a direct test. **Stop Worker** requests cancellation using the existing listener/render behavior.

Unreal's runtime plugin is installed into the explicitly registered project at render time; that project and the queue/output locations must be writable. The diagnostics use short-lived temporary write probes in those configured folders. Project downloading is not implemented by this GUI and remains off by default; do not treat the existing checkbox as a completed download feature.

## Persistent state and replacing the EXE

Worker settings and logs live in `%LOCALAPPDATA%\DefectStudio\RenderWorkerV2`. Cloud connection settings remain in the separate V2 location `%LOCALAPPDATA%\DefectStudio\RenderFarmV2\cloud_connection.json`. Nothing is saved in the executable's temporary extraction folder. The portable build starts with its own worker preferences; it does not automatically import the old pilot's settings or development-checkout registrations. Existing V2 connection settings for the same Windows user can still be reused.

Stop the worker and close it before replacing the EXE. Copy the new EXE over the old one, then reopen it; saved preferences remain. Copying the EXE to another computer does not copy credentials or machine paths. Automatic startup, crash recovery and self-updates are not included in this preview.

## Build

On Windows, install Python 3.13 for the build machine only. Run `build_worker.bat` or:

```powershell
powershell -NoProfile -File tools\build_worker.ps1 -Mode folder
powershell -NoProfile -File tools\build_worker.ps1 -Mode single
```

The build installs pinned dependencies into the worker's `.venv`. The folder build is under `dist/folder/RenderWorkerV2`; the distributable single EXE is `dist/single/RenderWorkerV2.exe`. `packaging/RenderWorkerV2.spec` uses an explicit resource allowlist; it does not include local settings, credentials, jobs, projects.json or production assets.

## Validate the exact artifact

The windowed executable accepts `--self-test REPORT.json`, which uses temporary synthetic settings to test the actual V2 GUI, registration persistence, default downloads-off, bundled resources, animation loading, and external process launch. It does not contact the dispatcher or render.

`tools/validate_portable_worker.py --exe PATH --output NEW_DIRECTORY` copies the single EXE outside its build tree, removes Python/Git and Defect environment configuration from the test process, supplies a fresh Local AppData location, launches from Windows' directory, and tests the artifact again after replacement. The self-test verifies preference persistence within its own two launches; replacement testing alone is not a substitute for a real user's saved-profile upgrade test.

Supply both `--bishop-settings SETTINGS.json` and `--bishop-job JOB.json` to explicitly opt in to a real Bishop render. This creates a new isolated filesystem queue and output tree, reads only the selected Bishop registration, disables downloads and invokes the EXE's `claim-once` command. It never connects to the production queue. The validation expects 40 nonempty EXR files for the existing development-shot fixture.

For controlled diagnostics, `RenderWorkerV2.exe render ...` forwards to the registered local render command. `RenderWorkerV2.exe claim-once --settings FILE --worker NAME --report FILE [--cloud]` claims at most one job; use it only against a deliberately configured queue. Windowed command output goes to the persistent worker log; the claim command writes a JSON receipt and exits nonzero when no job completes.

## Release limits

This preview is unsigned. It must still be checked under the destination computers' Windows security policies and endpoint protection. No signing certificate, remote V2 deployment or production migration is included. Same-machine tests with a fresh settings directory and restricted PATH are useful evidence but are not a second-machine acceptance test. The security audit's server-side project authorization and unique machine credentials remain separate hardening tasks.
