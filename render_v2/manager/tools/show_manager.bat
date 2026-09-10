@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"

py -3 -m portable_pipe_tools.apps.show_manager_app

endlocal
