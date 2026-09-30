Render Worker V2 - Python/batch distribution

Double-click tools\render_worker_v2.bat in the Defect Tools checkout.
The root run_worker_v2.bat is an alias for the same launcher.
Keep tools and render_v2 together; copying only the BAT is not sufficient.

Requirements:
- Windows and Python 3.11 or newer with Tcl/Tk (Tkinter).
- The launcher uses the worker's .venv if present, otherwise py -3 or python.
- No pip packages, PyInstaller, or EXE build are required.
- Unreal Engine, project files, required plugins and Dropbox access must exist.
- Install Git for Windows with Git LFS and authenticate access to the project
  and plugin repositories. Each render pulls the current branch's upstream,
  updates pinned submodules, and downloads LFS assets. Update failures prevent
  rendering. Commit or resolve local edits in Anchorpoint before starting.

First run:
1. Select the Dropbox project root.
2. Set UnrealEditor-Cmd.exe (UE 5.8 detection and Scan remain available).
3. Register each local Unreal project using +.
4. Click Check Setup, resolve any messages, then Start Worker.

The company worker-only V2 connection is included with the source at
render_v2\worker\worker_company_connection.json. No credential setup is needed.
V2 uses the separate company SQL service only; Dropbox does not coordinate jobs.

Settings/logs: %LOCALAPPDATA%\DefectStudio\RenderWorkerV2
Existing EXE settings are reused. Older source preferences are imported on GUI
startup only when the corresponding per-user settings file does not exist.
Stop and close the worker before updating the checkout.

Diagnostics (from the Defect Tools root):
tools\render_worker_v2.bat --self-test "%TEMP%\worker-v2-selftest.json"
The self-test uses synthetic projects; it does not claim jobs or render.

Project downloads, automatic startup and automatic worker software updates are not implemented
by this GUI. A second-computer Python-launch/render acceptance test is pending.
