@echo off
setlocal
set "PYTHONPATH=%~dp0src"
py -3 -m portable_pipe_tools.render_farm.registered_render %*
set "registeredRenderExit=%ERRORLEVEL%"
endlocal & exit /b %registeredRenderExit%
