@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"

where pyw.exe >nul 2>&1
if errorlevel 1 (
    start "" powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('AutoComp could not find the Python windowed launcher (pyw.exe). Please install Python with the Windows launcher enabled.','Auto Comp - Natron')"
    exit 1
)

start "" /D "%REPO_ROOT%" pyw.exe -3 -m portable_pipe_tools.apps.auto_comp_natron_app %*

endlocal
exit 0
