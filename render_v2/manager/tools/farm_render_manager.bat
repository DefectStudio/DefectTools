@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"

py -3 -m portable_pipe_tools.apps.farm_render_manager_app %*
set "FARM_RENDER_MANAGER_EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %FARM_RENDER_MANAGER_EXIT_CODE%
