# Render Worker V2 distribution

As of September 21, 2026, distribute Python source and a batch launcher.
The released EXE and PyInstaller build recipes have been removed. Earlier EXE
validation reports are historical evidence, not current installation instructions.

## Install and launch

1. Install Python 3.11+ for Windows with Tcl/Tk and the Python launcher.
2. Obtain the Defect Tools checkout, including its LFS-managed animation assets.
   Keep the `tools` and `render_v2` directories in their original layout.
3. Double-click `tools/render_worker_v2.bat`. It checks Python/Tk availability
   and runs `portable_pipe_tools.apps.worker_v2_launcher` from the V2 source root.
   No pip packages or build step are required. Startup failures remain visible
   in the console and application failures are written to the worker log.
4. Select the Dropbox root, set UnrealEditor-Cmd.exe, and add local projects.
   UE 5.8 auto-detection and the manual Scan button behave as before.
5. Click Check Setup, then Start Worker when ready to claim jobs.

Unreal, project assets and required plugins must already be installed. The worker
injects its minimal Unreal runtime into the selected project at render time.
Automatic project discovery/downloads, startup and updates are not implemented
by the registered-project GUI. As of September 30, Git for Windows with Git LFS
and preconfigured repository authentication are required. Before each render,
the current project branch is fast-forwarded to its configured upstream, pinned
submodules are updated recursively, and root/submodule LFS assets are hydrated.
Local tracked edits, detached HEAD, missing upstream, divergence, failed downloads
or authentication errors block rendering. Untracked files are preserved and no
branch switch, reset, clean or stash is performed. The clone/download checkbox
does not disable these updates to already registered checkouts.

## Company connection and settings

`render_v2/worker/worker_company_connection.json` is intentionally included in
Git with the batch/source release. It replaces the company worker credential
formerly embedded in the EXE; no per-artist credential provisioning is needed.
It contains only `api_url` and `worker_token`. Anyone with the checkout can read
this shared worker credential. Manager, submitter, and administrative profiles
remain separate and ignored. Rotate the shared worker token by updating this
file and distributing the updated checkout.

The service is `https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev`.
V1 is rejected, and there is no Dropbox/filesystem job-coordination fallback.
The worker does not use leftover machine service profiles or environment tokens.

Settings and logs remain in `%LOCALAPPDATA%/DefectStudio/RenderWorkerV2`.
Existing EXE users retain their registered projects and preferences. Older source
settings (`worker_v2.json`, `render_worker_local_save.json`) are copied from
`LocalSaveFiles` on GUI launch only if the corresponding per-user file is absent.
Stop the worker before updating the checkout; reopening uses the updated Python.

## Diagnostics

From the Defect Tools root:

```bat
tools\render_worker_v2.bat --self-test "%TEMP%\worker-v2-selftest.json"
tools\render_worker_v2.bat check-setup --report "%TEMP%\worker-v2-setup.json"
```

The self-test checks the actual GUI with synthetic temporary registrations,
settings reload, animation and runtime resources, and external process startup.
It does not contact SQL, claim work, or render. Check Setup checks configured
paths and company SQL access without claiming jobs.

The `render` and `claim-once` commands remain available for explicitly requested
render tests. `claim-once --worker NAME --report FILE` can claim and render a
real SQL job. The batch file forwards arguments and returns the Python exit code.

Run `render_v2/worker/test_worker.bat --no-pause` for regression tests.
The previous hosted Bishop acceptance used the EXE. A Python/batch render test
on another physical computer remains outstanding.

September 21 validation: all 221 worker tests passed. The tools launcher and both
aliases passed the GUI self-test. A copied source distribution also passed from
an unrelated working directory with spaces in its path, no virtual environment,
fresh user settings, and no separately provisioned connection. A restricted-PATH
check confirmed startup without Git on PATH; absent Python produces actionable
guidance and exit code 1. The bundled company connection authenticated with the
hosted service as the worker role; the database health check was connected.
No jobs were claimed and no real renders were started during these checks.
