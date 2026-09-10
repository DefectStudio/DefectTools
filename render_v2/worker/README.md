# Render Worker

**Automatic claiming is connected:** Start Worker polls registered shows using
filesystem claims or V2 cloud leases. See [registered queue claiming](docs/registered-queue-claiming.md).

**Registered local rendering is now available:** select a saved project and use
**Render job file…**. See [setup and Bishop validation](docs/registered-local-rendering.md).

Worker V2 now lives in the Defect Tools repository at `render_v2/worker`.
See [consolidated setup](../README.md); it supersedes older separate-repository
paths below. Use the root `run_worker_v2.bat` for the current GUI review with
manual local project registration.

The packaged setup is: copy `RenderWorker.exe` to a folder, run it, and configure machine access once. Python and the worker's Unreal runtime scripts are included. The worker discovers or fetches projects before rendering.

## Current status

The existing worker has been separated from Defect Tools. It includes the worker UI, cloud connection setup, job execution, leases/recovery, Git update code, engine discovery, sprites, and tests. It does not need a sibling Defect Tools checkout to import or run.

V2 now has direct project jobs, a reloadable project catalog, existing-repository discovery, managed Git/LFS preparation, engine discovery, and a new setup window. It automatically discovered Bishop and successfully rendered all 40 frames of `ZZZ850`; see [provisioning validation](docs/project-provisioning-validation.md). Cloud job leasing is not yet connected to automatic project preparation.

The worker installs its own minimal Unreal executor into each managed checkout. It does not require installing or linking the artist tool suite. Project-tracked plugins arrive with the project; engine installation and licensed third-party plugins remain machine prerequisites.

## Setup once per computer

1. Install Git with Git LFS and the Unreal versions your projects require.
2. Authenticate Git for access to the studio's project repositories. Background preparation never prompts for credentials.
3. Copy the built `dist/RenderWorker.exe` to a folder and double-click it. Choose a workspace and output folder. Leave the catalog blank for the default, or enter a shared catalog file or HTTPS catalog URL.
4. Select **bishop**, enter **ZZZ850**, and click **Render shot**.

**Prepare project** downloads and checks the project without rendering. **Stop** cancels preparation or rendering. The EXE saves settings to `%LOCALAPPDATA%\DefectRenderWorker\worker_v2.json`, so replacing the EXE preserves setup. Adding a project requires one entry in the shared catalog; workers reload it before each job. See [EXE installation and builds](docs/windows-package.md).

Source users can install Python and run `run_worker.bat`; source launches continue to save settings in the ignored `LocalSaveFiles/worker_v2.json`.

On every preparation attempt, the worker first rereads Unreal Editor's recent-project list and the project folders recorded by Unreal Editor and Epic Launcher. It then checks its own remembered location and common project folders. It reuses a repository only when its remote, project file, and branch match the catalog. Existing tracked edits stop the job; untracked files are preserved. It never switches an existing checkout's branch automatically. Optional `discovery_roots` in machine settings supplies other fallback search locations.

```bat
render_project.bat list
render_project.bat prepare --project bishop --workspace F:\RenderWorkerWorkspace
render_project.bat render --project bishop --shot ZZZ850 --workspace F:\RenderWorkerWorkspace
```

Add `--catalog` or `--output-root` to override saved settings. Initial clones use `--depth 1 --single-branch`; subsequent updates use `git pull --ff-only` and fetch changes needed since the previous tip, without fetching the project's older history. There is no separate asset hash scan. The worker records the rendered commit and holds a project lock through rendering. It refuses unmanaged folders or local changes and can resume interrupted preparation. First setup needs substantial time and space: Bishop contains about 235 GiB of LFS assets. An optional `lfs_cache_roots` list in machine settings reuses existing Git LFS objects; it is not required.

Each render writes a unique directory under `renders/<project>/<shot>/`, containing request, preparation receipt, logs, job details, outputs, and a result receipt. The current pilot produces EXR frames and disables project graph script callbacks so development renders do not trigger production publishing.

## Local development

See [project catalog configuration](docs/project-catalog.md) for adding projects centrally and setting up machine storage.

Requirements: Windows, Python 3.11 or newer with Tkinter and the `py` launcher, and Git for Windows. Actual renders also need a compatible Unreal installation and project assets; LFS projects need Git LFS.

- `test_worker.bat` runs the repository's tests without contacting the farm or starting a render.
- `run_worker.bat` opens the worker UI.
- `configure_cloud_dispatcher.bat` opens the existing farm connection setup.
- `tools/render_worker.bat --help` shows the worker CLI.

The new launcher runs direct project jobs without a worker-repository upstream. The inherited farm queue client under `tools/` still requires a configured upstream and one local project. This repository is intentionally local-only. Automatic engine installation, worker self-updates, cloud provisioning integration, and unattended service startup remain later milestones.

There is no package installation step for source development; launchers set the local `src` path. Python imports temporarily retain the `portable_pipe_tools` namespace to preserve the existing tested code during extraction.

## V2 acceptance test

Request Bishop `ZZZ_000_0850`. The worker must discover an existing matching repository and reuse it, or clone and hydrate one when none exists, then prepare its runtime and render without manual project selection or artist-tool linking. Test the discovery and fresh-clone paths separately and identify which path produced each result.

See [the implementation plan](docs/render-worker-v2-plan.md), [the first validation report](docs/render-worker-v2-validation.md), and [extraction notes](docs/repository-extraction.md).

Machine settings, credentials, downloaded projects, renders, and logs must stay outside Git. No credentials or local settings were copied during extraction.
