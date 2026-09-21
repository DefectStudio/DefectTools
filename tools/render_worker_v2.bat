@echo off
setlocal
set "WORKER_ROOT=%~dp0..\render_v2\worker"
set "PYTHONPATH=%WORKER_ROOT%\src"

rem Prefer a local worker environment, then the Windows Python launcher.
set "WORKER_PYTHON=%WORKER_ROOT%\.venv\Scripts\python.exe"
set "WORKER_PYTHON_ARGS="
if exist "%WORKER_PYTHON%" goto check_python
set "WORKER_PYTHON="
set "WORKER_PYTHON_ARGS=-3"
for /f "delims=" %%P in ('where py 2^>nul') do if not defined WORKER_PYTHON set "WORKER_PYTHON=%%P"
if defined WORKER_PYTHON goto check_python
set "WORKER_PYTHON_ARGS="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined WORKER_PYTHON set "WORKER_PYTHON=%%P"
if not defined WORKER_PYTHON goto missing_python

:check_python
"%WORKER_PYTHON%" %WORKER_PYTHON_ARGS% -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto missing_python
goto launch

:missing_python
echo Render Worker V2 requires Python 3.11 or newer with Tcl/Tk.
echo Install Python for Windows with Tcl/Tk and the Python launcher enabled.
echo No pip packages or EXE build are required.
if "%~1"=="" pause
exit /b 1

:launch
pushd "%WORKER_ROOT%"
if errorlevel 1 (
    echo Cannot find the worker source. Keep tools and render_v2 together in Defect Tools.
    if "%~1"=="" pause
    exit /b 1
)
"%WORKER_PYTHON%" %WORKER_PYTHON_ARGS% -m portable_pipe_tools.apps.worker_v2_launcher %*
set "WORKER_EXIT_CODE=%ERRORLEVEL%"
popd
if not "%WORKER_EXIT_CODE%"=="0" (
    echo Render Worker V2 exited with code %WORKER_EXIT_CODE%.
    echo Details: %LOCALAPPDATA%\DefectStudio\RenderWorkerV2\logs\worker.log
    if "%~1"=="" pause
)
endlocal & exit /b %WORKER_EXIT_CODE%
