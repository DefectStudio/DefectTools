@echo off
setlocal

for %%I in ("%~dp0..") do set "TOOLS_ROOT=%%~fI"
set "PORTABLE_NATRON_PLUGINS=%TOOLS_ROOT%\natron_plugins"
set "NATRON_EXE=F:\Natron\bin\Natron.exe"

if defined NATRON_PLUGIN_PATH (
    set "NATRON_PLUGIN_PATH=%PORTABLE_NATRON_PLUGINS%;%NATRON_PLUGIN_PATH%"
) else (
    set "NATRON_PLUGIN_PATH=%PORTABLE_NATRON_PLUGINS%"
)

if not exist "%NATRON_EXE%" (
    echo Natron was not found at "%NATRON_EXE%".
    exit /b 1
)

start "" "%NATRON_EXE%" %*

endlocal

