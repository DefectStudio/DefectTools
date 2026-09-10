@echo off
setlocal
set "PYTHONPATH=%~dp0src"
py -3 -m portable_pipe_tools.render_farm.project_worker %*
set "WORKER_EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %WORKER_EXIT_CODE%
