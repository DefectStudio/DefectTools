@echo off
setlocal
set "UPDATER=%~dp0UpdateQuickWidgetTools.ps1"
if not exist "%UPDATER%" (
    echo UpdateQuickWidgetTools.ps1 is missing. Keep it beside this launcher.
    pause
    exit /b 1
)
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File "%UPDATER%" %*
set "UPDATER_EXIT=%ERRORLEVEL%"
if not "%UPDATER_EXIT%"=="0" (
    echo The updater could not start. Check Git for Windows and access to I:\AICache.
    pause
)
endlocal & exit /b %UPDATER_EXIT%
