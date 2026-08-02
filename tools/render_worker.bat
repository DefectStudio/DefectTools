@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"

py -3 -m portable_pipe_tools.render_farm.worker %*
set "RENDER_WORKER_EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %RENDER_WORKER_EXIT_CODE%
