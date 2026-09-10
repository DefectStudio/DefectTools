@echo off
setlocal
set "PYTHONPATH=%~dp0..\src"
start "" pyw -3 "%~dp0manager_v2_local.py"
endlocal
