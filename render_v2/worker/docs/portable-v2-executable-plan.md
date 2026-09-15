# Portable Render Worker V2 executable

Source assessment and proposed implementation plan — September 15, 2026.

## Answer

Yes: the current code supports the foundation for a portable Windows executable. It is not yet the finished V2 distribution. The existing PyInstaller build launches the older `ProjectWorkerApp` pilot, while the registered-project GUI and automatic claiming live in `RenderWorkerV2App`. Running the existing build unchanged would package the wrong interface and workflow.

Target delivery: a Windows x64 `RenderWorkerV2.exe` that can be copied into a folder and launched by a standard user, without Python, pip, a Defect Tools checkout, or developer setup on the destination computer. Keep machine settings and logs in that user's Local AppData so replacing or moving the executable does not discard configuration.

The executable can make the worker portable; it cannot make Unreal, project assets, credentials, and network access appear automatically. A fresh computer still needs those prerequisites and a short first-run setup. Subsequent launches should use the saved configuration.

## What already exists

| Area | Existing support | Remaining work |
|---|---|---|
| Executable build | Pinned PyInstaller build requirements, Windows build script, single-file/windowed spec | Point a V2 entry point at the current GUI; produce an explicitly named/versioned V2 artifact |
| Embedded resources | Spec includes the Python Unreal runtime plugin; rendering locates it through `resource_root()` | Verify every required plugin/resource in the actual frozen build; remove the legacy project catalog from the new workflow |
| Persistent configuration | Frozen-mode paths use Local AppData; V2 saves engine choice, Dropbox root, project registrations and listener preferences | Establish a V2-specific data location and any explicit migration needed from the pilot; never bundle this workstation's settings |
| Unreal subprocess startup | Existing entry point calls the helper that removes PyInstaller DLL/PATH interference before launching external programs | Preserve this behavior in the new entry point and verify it with Unreal |
| Rendering | Current GUI supports worker-initiated filesystem/cloud claiming and registered local projects | Exercise those exact paths from the EXE, independently of the development checkout |
| Local project support | Runtime installation supports copied projects and treats Git as optional | Verify startup/rendering with no Git on PATH; require writable project/plugin and render-output locations |
| Diagnostics | Pilot entry point has startup logging and a self-test | Replace pilot-specific checks with V2 GUI, resource, configuration and subprocess checks |

Evidence: [build specification](<F:/Defect Tools/render_v2/worker/packaging/RenderWorker.spec>), [current packaged entry point](<F:/Defect Tools/render_v2/worker/packaging/worker_entry.py>), [frozen-runtime helpers](<F:/Defect Tools/render_v2/worker/src/portable_pipe_tools/app_runtime.py>), [V2 GUI](<F:/Defect Tools/render_v2/worker/src/portable_pipe_tools/apps/render_worker_v2_app.py>), [runtime installation](<F:/Defect Tools/render_v2/worker/src/portable_pipe_tools/render_farm/project_render.py>).

## Minimum setup on another computer

1. Have the supported Unreal version and GPU drivers installed. Use the existing one-time UnrealEditor-Cmd detection; if it finds nothing, prompt for the executable. Do not repeatedly scan or change an explicit choice.
2. Have the necessary local Unreal project files and authorized Dropbox/show folders available. Select the Dropbox root and manually register each local `.uproject`. Do not discover project repositories automatically.
3. For cloud claiming, supply a reachable V2 dispatcher URL and worker credential. The current localhost development endpoint is not a company deployment: on another machine, localhost points to that machine. Filesystem queue mode is an alternative when explicitly configured.
4. Run a readiness check, then start the worker. Check engine/project compatibility, assets, plugin write access, renderFarm/output access, free space and the selected queue connection. Report actionable errors in the GUI.

The EXE carries Python/Tk and the worker's own runtime resources. It does not carry Unreal, production assets, Dropbox login state, or company secrets. Python is needed on the build computer only. Git and Git LFS belong to any separately enabled download/update workflow, not the registered-local-project baseline. The current registered GUI does not implement project downloading; packaging should not imply that its checkbox makes this feature complete. Keep downloads off by default.

## Implementation sequence

1. **Create the V2 executable entry point.** Launch `RenderWorkerV2App`, preserve frozen subprocess setup and startup error logging, and handle multiprocessing initialization if retained. Ensure importing the entry point never starts the worker or renders a job. Keep V1 launchers untouched.
2. **Make startup independent of the checkout.** Bundle only application/runtime files and license notices. Remove dependencies on adjacent source folders, project catalogs and development-machine paths. Keep mutable settings, queue spool and logs out of the executable's temporary extraction directory. Do not package saved machine credentials or registrations.
3. **Finish first-run readiness.** Present the existing engine and project registration controls with clear missing-prerequisite messages. Add a connection check that does not claim a job. Save successful choices. Do not grant elevated privileges or silently download projects to make checks pass.
4. **Build and validate.** First validate a PyInstaller folder build to diagnose missing files, then build the single EXE and rerun acceptance against that exact artifact. Update build/self-test instructions and version metadata. Code signing can be part of distribution preparation; signing and endpoint-security compatibility must be verified on actual target machines.
5. **Deliver a tested artifact.** Copy only the EXE to a second machine, complete first-run setup, render Bishop `ZZZ_000_0850` through the isolated V2 queue, then replace the EXE and confirm settings survive. Record supported Windows/Unreal versions and tested machine details with the release.

PyInstaller bundles the Python interpreter, supports folder and single-executable distributions, and recommends validating folder mode before single-file mode. Single-file execution extracts bundled files temporarily; it is not an installation of Python on the destination machine. [Official PyInstaller packaging behavior](https://pyinstaller.org/en/stable/operating-mode.html).

## Acceptance criteria

- A clean Windows account with no Python, no Git and no Defect Tools checkout opens the V2 GUI from a copied EXE. Test a path containing spaces and a working directory unrelated to the EXE.
- A fresh machine starts with no developer-specific project paths, saved users, credentials or localhost connection presented as ready for production.
- Missing Unreal, inaccessible folders, insufficient permissions and invalid/unavailable dispatcher settings yield readable errors and persistent diagnostic logs.
- Explicit registrations, engine selection and listener preferences survive restarting and replacing the EXE. Two different users/machines retain their own configuration.
- The frozen worker claims only its configured eligible local projects in the normal workflow, renders the Bishop test shot, produces expected output and completes the job through the isolated V2 service. Check Stop/cancellation and restarting after a failed render. This functional check does not replace server-side security authorization tests.
- No source checkout or build-machine resource path is used during the copied-artifact test. Verify the EXE's own bundled plugin installation and external Unreal startup.
- V1 and its production queue are unaffected. A real clean-machine render is required before claiming the distribution “just works”; a development-machine self-test alone is insufficient.

## Related work that packaging does not complete

The company needs a reachable, separately provisioned V2 dispatcher if cloud mode is chosen. The security audit's per-machine credentials and server-enforced project permissions also remain separate hardening work; local project registration is not authorization. Never embed a manager token in the EXE.

Automatic start after login, restart after a crash, unattended updates and project downloading are separate features. The first executable should preserve settings across manual replacement. Add unattended behavior explicitly after the basic copied-artifact render passes.

No executable was built during this assessment. The proposed next implementation step is to replace the pilot packaging entry point with the current V2 GUI and verify its frozen startup.
