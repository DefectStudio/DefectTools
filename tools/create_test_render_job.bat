@echo off
setlocal

set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"

py -3 -m portable_pipe_tools.render_farm.test_job %*
set "TEST_JOB_EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %TEST_JOB_EXIT_CODE%
