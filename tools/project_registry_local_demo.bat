@echo off
setlocal
set "PYTHONPATH=%~dp0..\src"
start "" pyw -3 "%~dp0project_registry_local_demo.py"
endlocal
