# V2 GUI starting point

**Latest project setup:** [Dropbox projects](dropbox-projects.md) supersedes the
free-text project ID editor below. Project names now come from the selected
Dropbox root; local Unreal project locations are still manually registered.

Run `run_worker_v2_gui.bat` to open **Render Worker V2 — Layout Review**.

The interface is copied from `src/portable_pipe_tools/apps/render_worker_app.py` into `render_worker_v2_app.py` for the September 10 GUI review. It retains the V1 setup fields, controls, layout, activity sprites, and log. The only visual identity changes are the V2 heading and window title.

This review window starts stopped, does not check for updates or start a listener, and disables farm action buttons. The engine preference and manually registered project list save to V2 settings; other setup fields can be explored without saving over V1 settings. It does not scan for or download projects. The original V1 module, current direct-job launcher, and packaged EXE remain separate while we discuss the GUI changes.

**UnrealEditor-Cmd.exe** auto-detects Unreal 5.8 only on the first launch without a saved V2 engine preference. In order, it checks the standard Epic installation location, Epic's installed-engine manifest, and Windows registry engine registrations. It verifies that the executable exists and checks build-version metadata when available. If no 5.8 installation is found, the field is blank; it does not fall back to a saved V1 path or another engine version. This detects engine installations only, not project folders.

The detection result is immediately saved, including a blank result. Later launches load that preference without repeating detection, even if the engine moves or is removed. **Browse...** saves a manual selection; typed edits save when leaving the field, pressing Enter, or closing the window. Clearing the field also persists and does not trigger detection again.

Source GUI preferences live in `LocalSaveFiles/worker_v2.json`, alongside existing V2 configuration. The engine key is `unreal_editor_cmd`; key presence records that first-time setup is complete. Packaged launches use `%LOCALAPPDATA%\DefectRenderWorker\worker_v2.json`. Other saved V2 settings are preserved.

## Projects on this worker

The project list sits directly below Worker Name. **+** opens Add project; double-click a row (or press Enter on a selected row) to edit it. **OK** validates and immediately saves the registration, then updates the list. **Cancel** discards dialog edits. **−** removes the selected registration and saves the updated list without deleting project or output files.

Each entry contains a project name, project ID matching submitted jobs, explicit local `.uproject` path, and the show's RenderFarm folder. The existing farm output mapping uses RenderFarm's parent as the show output root. The worker-wide Unreal executable applies to these projects; shot, sequence, and render settings belong to individual jobs.

**Allow project downloads** defaults to off for each new entry. Checking it enables Repository URL and Git branch fields, which must be valid to save the permission. This iteration saves configuration only; the new list is not yet connected to job execution or downloading. No catalog entries or discovered locations are automatically registered.

Registrations are stored under `registered_projects` in the same V2 settings file as the engine preference. Duplicate project IDs are rejected. Missing files or folders are shown in the list's Location status column; their registrations remain available for editing when a drive is disconnected or a project has not yet been copied. Location status verifies the two paths only and does not claim the project is ready to render.

The previous single-project setup fields remain visible for the ongoing V1-to-V2 layout discussion. The new per-project registrations will replace their role when job execution is connected.
