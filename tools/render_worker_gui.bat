@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"
set "PORTABLE_PIPE_TOOLS_REPO_ROOT=%REPO_ROOT%"

:launch_render_worker
py -3 -m portable_pipe_tools.apps.render_worker_app %*
set "RENDER_WORKER_GUI_EXIT_CODE=%ERRORLEVEL%"

if "%RENDER_WORKER_GUI_EXIT_CODE%"=="75" (
    echo Render Worker update installed. Restarting...
    goto launch_render_worker
)

endlocal & exit /b %RENDER_WORKER_GUI_EXIT_CODE%
