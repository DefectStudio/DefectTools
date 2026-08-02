@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"

py -3 -m portable_pipe_tools.apps.render_worker_app %*
set "RENDER_WORKER_GUI_EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %RENDER_WORKER_GUI_EXIT_CODE%
