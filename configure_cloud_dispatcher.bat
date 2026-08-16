@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "PYTHONPATH=%REPO_ROOT%src"

py -3 -m portable_pipe_tools.apps.cloud_dispatcher_setup_app
set "CLOUD_SETUP_EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %CLOUD_SETUP_EXIT_CODE%
