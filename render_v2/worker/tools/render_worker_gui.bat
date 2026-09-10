@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"
set "PORTABLE_PIPE_TOOLS_REPO_ROOT=%REPO_ROOT%"

rem Explorer can keep the PATH it had before Git was installed. Add the
rem standard Git for Windows locations so double-click launches still work.
if exist "%LocalAppData%\Programs\Git\cmd\git.exe" set "PATH=%LocalAppData%\Programs\Git\cmd;%PATH%"
if exist "%ProgramFiles(x86)%\Git\cmd\git.exe" set "PATH=%ProgramFiles(x86)%\Git\cmd;%PATH%"
if exist "%ProgramFiles%\Git\cmd\git.exe" set "PATH=%ProgramFiles%\Git\cmd;%PATH%"

where git.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: Git for Windows was not found.
    echo Install Git or add its cmd folder to PATH, then reopen this launcher.
    pause
    endlocal & exit /b 1
)

:launch_render_worker
py -3 -m portable_pipe_tools.apps.render_worker_app %*
set "RENDER_WORKER_GUI_EXIT_CODE=%ERRORLEVEL%"

if "%RENDER_WORKER_GUI_EXIT_CODE%"=="75" (
    echo Render Worker update installed. Restarting...
    goto launch_render_worker
)

endlocal & exit /b %RENDER_WORKER_GUI_EXIT_CODE%
