@echo off
setlocal
set "PYTHONPATH=%~dp0src"
if exist "%ProgramFiles%\Git\cmd\git.exe" set "PATH=%ProgramFiles%\Git\cmd;%PATH%"
if exist "%LocalAppData%\Programs\Git\cmd\git.exe" set "PATH=%LocalAppData%\Programs\Git\cmd;%PATH%"
py -3 -m portable_pipe_tools.apps.project_worker_app %*
set "WORKER_EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %WORKER_EXIT_CODE%
