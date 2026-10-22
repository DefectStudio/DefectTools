@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Manual Render Hero Chooser
set "PYTHONPATH=%~dp0..\src"
set "PYTHONDONTWRITEBYTECODE=1"
set "TEMP=I:\AICache\ManualRenderHeroChooser\runtime"
set "TMP=%TEMP%"
if not exist "I:\AICache\" (
    echo ERROR: I:\AICache is unavailable. Restore access to that folder and try again.
    pause
    exit /b 1
)
if not exist "%TEMP%\" mkdir "%TEMP%"
if not exist "%TEMP%\" (
    echo ERROR: Cannot create the working folder at %TEMP%.
    pause
    exit /b 1
)
py -3 -B -m portable_pipe_tools.apps.manual_render_hero_chooser %*
if errorlevel 1 (
    echo.
    echo Manual Render Hero Chooser could not start or stopped with an error.
    echo This tool needs Python 3.11 or newer with Tkinter, like the other DefectTools apps.
    pause
    exit /b 1
)
endlocal
