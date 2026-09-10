@echo off
setlocal
set "PYTHONPATH=%~dp0src"
start "" pyw -3 "%~dp0tools\manager_v2_local.py"
endlocal
