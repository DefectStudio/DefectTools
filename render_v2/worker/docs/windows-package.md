# Windows EXE

> Historical pilot documentation. The current registered-project worker is
> `RenderWorkerV2.exe`; use [Portable Worker V2](portable-worker-v2.md).
> Its default build does not use the catalog, project discovery, or downloads described below.

`dist/RenderWorker.exe` is a portable Windows x64 application containing Python, Tkinter, the worker application, the default project catalog, and the Unreal runtime scripts. Copy the EXE to a folder and double-click it. No Python installation, pip command, source checkout, or administrator access is needed to launch the worker.

## First-time setup

1. Install Git for Windows with Git LFS and authenticate access to the project's Git remote. The worker discovers Git through PATH, its installation registry entry, or common installation folders.
2. Install the required Unreal Engine version and any required engine plugins. The worker discovers installed engines; it does not install Unreal.
3. Run `RenderWorker.exe`. Choose the workspace for downloaded projects and the output folder. The default workspace is `RenderWorkerWorkspace` in the Windows user's home folder.
4. Leave **Catalog (blank = default)** blank to use the included catalog. A `projects.json` beside the EXE overrides the included catalog. Alternatively, enter a shared catalog file or HTTPS URL; that is the option for centrally adding projects without replacing each worker's EXE.
5. Select a project and click **Prepare project**, or enter a shot and click **Render shot**. Bishop's development-shot alias is `ZZZ850`.

Each preparation rereads Unreal Editor and Epic Launcher project metadata before checking remembered locations and other discovery roots. A matching existing repository is reused and updated with `git pull --ff-only`; otherwise the worker makes a shallow clone. Local tracked changes stop preparation. Rendering requires Git credentials that work without a prompt.

Settings persist in `%LOCALAPPDATA%\DefectRenderWorker\worker_v2.json`. The blank default catalog selection is saved as blank, so it remains valid after restarting or replacing the EXE. Logs rotate under `%LOCALAPPDATA%\DefectRenderWorker\logs\worker.log`. Per-render logs and receipts remain in the selected output folder.

To update this local package, close the worker and replace the EXE. Settings are per Windows user, so a different user account needs its own setup. Source launches retain the separate repository-local `LocalSaveFiles/worker_v2.json` settings.

This package supports the current direct project jobs. Cloud leasing integration, automatic worker updates, engine installation, and unattended service startup remain separate work.

## Build

On Windows, install Python 3.13 with the `py` launcher and run:

```bat
build_worker.bat
```

The build creates `.venv` if needed, installs the pinned dependencies from `requirements-build.txt`, and runs `packaging/RenderWorker.spec`. The output is `dist/RenderWorker.exe` (approximately 12 MB). Generated build files are ignored by Git. This is a local build; no release is uploaded.

PyInstaller packages the Python interpreter and extracts bundled resources when the EXE starts. Resource paths and persistent settings paths are separate. Before starting Git or Unreal, the entry point clears the bundled DLL search directory so external programs use their own dependencies. See PyInstaller's [operating model](https://pyinstaller.org/en/stable/operating-mode.html), [runtime paths](https://pyinstaller.org/en/stable/runtime-information.html), and [external-program requirements](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html).

## Diagnostics and command-line jobs

The EXE is windowed. Command-line output is written to the worker log instead of a console. In PowerShell, use `Start-Process -Wait -PassThru` when an exit code is needed:

```powershell
$worker = Start-Process -FilePath .\RenderWorker.exe -ArgumentList '--self-test C:\Temp\worker-self-test.json' -Wait -PassThru
$worker.ExitCode
```

The self-test checks bundled resources, GUI startup, default catalog loading, settings saving and reloading, and external Git/LFS availability. It uses temporary settings and does not fetch projects or render. Check `external_programs` in its JSON report separately: missing Git/LFS is reported without failing the bundle check.

The existing `list`, `prepare`, and `render` commands are also available:

```bat
RenderWorker.exe list
RenderWorker.exe prepare --project bishop --workspace F:\RenderWorkerWorkspace
RenderWorker.exe render --project bishop --shot ZZZ850 --workspace F:\RenderWorkerWorkspace
```

Optional `--settings`, `--catalog`, and `--output-root` arguments override defaults.

## Validation on 2026-09-09

- All 157 repository tests passed.
- Copied only the EXE out of the repository into `F:\RenderWorkerPackageTest\exe-v2`. Launched with PATH restricted to Windows/System32 and with `PYTHONPATH` and `PYTHONHOME` removed. The packaged Python 3.13.2/Tk 8.6.15 application loaded Bishop successfully, saved and reloaded default catalog settings, and found Git/LFS.
- The packaged CLI discovered the existing Bishop checkout at `F:\Projects`, pulled main, prepared its Unreal runtime, and rendered `ZZZ850` using Unreal 5.8.2. The engine exited 0; all 40 EXR outputs passed validation. Production graph script callbacks were disabled. Existing tracked project files remained unchanged.
- Render receipt: `F:\RenderWorkerPackageTest\exe-v2\renders\bishop\ZZZ_000_0850\20260910T010130Z_f609bc42\result.json`. Diagnostic report: `F:\RenderWorkerPackageTest\exe-v2\self-test.json`.

This verifies independence from the worker source tree and installed Python on this computer. A separate clean Windows machine has not yet been tested.
