Render Worker V2 — 2.0.0-preview.1 (Windows x64 preview)

Local executable: F:\Defect Tools\tools\RenderWorkerV2.exe
Source and build tooling: F:\Defect Tools\render_v2\worker
Manager and SQL service source: F:\Defect Tools\render_v2\manager
The released executable is tracked with Git LFS, including its embedded company worker credential, as approved by the user.
Build with render_v2\worker\build_worker.bat; single-file builds copy the EXE here.

Copy RenderWorkerV2.exe to the destination computer and double-click it.
Python, Git and the Defect Tools repository are not required for local projects.
Unreal Engine, project files, required engine plugins and Dropbox access must already be available.

First run:
1. Select the Dropbox root using Browse to reveal the UnrealEditor-Cmd.exe row.
2. Set UnrealEditor-Cmd.exe to reveal the remaining controls, then use + to register each local Unreal project. UE 5.8 is detected once; use Scan beside Browse to detect it again.
3. Company SQL connection is embedded in this EXE. There is no connection setup or Dropbox job-coordination mode.
   Company service: https://defect-farm-api-v2.twilight-tooth-7b7c.workers.dev (separate V2 database).
4. Click Check Setup, resolve its messages, then Start Worker.

Settings/logs: %LOCALAPPDATA%\DefectStudio\RenderWorkerV2
The packaged EXE uses its embedded company V2 connection; no local connection file is needed.
Stop and close the worker before replacing the EXE. Settings survive replacement.
Do not copy another person's credentials or machine settings with this EXE.

This preview does not download projects, install Unreal, auto-start, or auto-update.
It is unsigned. A test on another physical machine is still required before broad rollout.
