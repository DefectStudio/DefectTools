@echo off
setlocal

set "DOCTOR_LAUNCHER=%~dp0..\src\portable_pipe_tools\defect_doctor\launch_defect_doctor.py"
if not exist "%DOCTOR_LAUNCHER%" goto missing_source

py -3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto try_python
py -3 "%DOCTOR_LAUNCHER%" %*
set "DOCTOR_EXIT_CODE=%ERRORLEVEL%"
goto finished

:try_python
python -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 goto missing_python
python "%DOCTOR_LAUNCHER%" %*
set "DOCTOR_EXIT_CODE=%ERRORLEVEL%"
goto finished

:missing_source
echo Cannot find Defect Doctor: "%DOCTOR_LAUNCHER%"
echo Keep the tools and src folders together in Defect Tools.
if "%~1"=="" pause
exit /b 1

:missing_python
echo Defect Doctor Chat Client requires Python 3.11 or newer with Tcl/Tk.
echo Install Python for Windows with Tcl/Tk and the Python launcher enabled.
if "%~1"=="" pause
exit /b 1

:finished
if not "%DOCTOR_EXIT_CODE%"=="0" (
    echo Defect Doctor Chat Client exited with code %DOCTOR_EXIT_CODE%.
    if "%~1"=="" pause
)
endlocal & exit /b %DOCTOR_EXIT_CODE%
