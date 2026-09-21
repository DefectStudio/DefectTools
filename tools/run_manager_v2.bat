@echo off
setlocal
set "MANAGER_ROOT=%~dp0..\render_v2\manager"
set "PYTHONPATH=%MANAGER_ROOT%\src"
set "MANAGER_PYTHON=%MANAGER_ROOT%\.venv\Scripts\python.exe"
set "MANAGER_PYTHON_ARGS="
if exist "%MANAGER_PYTHON%" goto check_python
set "MANAGER_PYTHON="
set "MANAGER_PYTHON_ARGS=-3"
for /f "delims=" %%P in ('where py 2^>nul') do if not defined MANAGER_PYTHON set "MANAGER_PYTHON=%%P"
if defined MANAGER_PYTHON goto check_python
set "MANAGER_PYTHON_ARGS="
for /f "delims=" %%P in ('where python 2^>nul') do if not defined MANAGER_PYTHON set "MANAGER_PYTHON=%%P"
if not defined MANAGER_PYTHON goto missing_python

:check_python
"%MANAGER_PYTHON%" %MANAGER_PYTHON_ARGS% -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto missing_python
goto launch

:missing_python
echo Render Farm Manager V2 requires Python 3.11 or newer with Tcl/Tk.
echo Install Python for Windows with Tcl/Tk and the Python launcher enabled.
if "%~1"=="" pause
exit /b 1

:launch
pushd "%MANAGER_ROOT%"
if errorlevel 1 (
    echo Cannot find Manager V2 source. Keep tools and render_v2 together in Defect Tools.
    if "%~1"=="" pause
    exit /b 1
)
"%MANAGER_PYTHON%" %MANAGER_PYTHON_ARGS% "%MANAGER_ROOT%\tools\manager_v2_company.py" %*
set "MANAGER_EXIT_CODE=%ERRORLEVEL%"
popd
if not "%MANAGER_EXIT_CODE%"=="0" (
    echo Render Farm Manager V2 exited with code %MANAGER_EXIT_CODE%.
    echo Log: %LOCALAPPDATA%\DefectStudio\RenderFarmManagerV2\logs\manager.log
    if "%~1"=="" pause
)
endlocal & exit /b %MANAGER_EXIT_CODE%
