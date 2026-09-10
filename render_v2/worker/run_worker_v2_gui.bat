@echo off
setlocal
set "PYTHONPATH=%~dp0src"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" -m portable_pipe_tools.apps.render_worker_v2_app
) else (
    start "" pyw -3 -m portable_pipe_tools.apps.render_worker_v2_app
)
endlocal
