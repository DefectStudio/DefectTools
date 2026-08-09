@echo off
setlocal EnableExtensions DisableDelayedExpansion

if /I "%~1"=="--install-child" goto :install_child
if /I "%~1"=="--help" goto :show_help

title DefectTools Installer
echo.
echo ============================================================
echo  DefectTools Render Node Installer
echo ============================================================
echo.
echo This will install Python 3.12, Git, and Git LFS, then download
echo the latest DefectTools main branch into this folder.
echo.

set "INSTALL_DIR=%~dp0"
set "INSTALLER_NAME=%~nx0"
set "TEMP_INSTALLER=%TEMP%\DefectToolsInstaller_%RANDOM%_%RANDOM%.bat"

copy /Y "%~f0" "%TEMP_INSTALLER%" >nul
if errorlevel 1 (
    echo ERROR: Could not create the temporary installer copy.
    pause
    exit /b 1
)

rem Run from a temporary copy so this folder can become a clean Git checkout.
start "DefectTools Installer" cmd /D /C call ""%TEMP_INSTALLER%" --install-child "%INSTALL_DIR%" "%INSTALLER_NAME%""
exit /b 0

:install_child
title DefectTools Installer
for %%I in ("%~2.") do set "INSTALL_DIR=%%~fI"
set "INSTALLER_NAME=%~3"
set "REPOSITORY_URL=https://github.com/DefectStudio/DefectTools.git"
set "GIT_EXE="
set "PYMANAGER_EXE="

echo.
echo [1/6] Checking Windows Package Manager...
where winget.exe >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: WinGet is not available on this computer.
    echo Install or update "App Installer" from the Microsoft Store,
    echo then run this installer again.
    goto :failed
)

echo.
echo [2/6] Installing the Python Install Manager...
winget install 9NQ7512CXL7T -e --source msstore --accept-package-agreements --accept-source-agreements --disable-interactivity
set "PATH=%LOCALAPPDATA%\Microsoft\WindowsApps;%PATH%"
for %%P in (pymanager.exe) do set "PYMANAGER_EXE=%%~$PATH:P"
if not defined PYMANAGER_EXE if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.PythonManager_3847v3x7pw1km\pymanager.exe" set "PYMANAGER_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.PythonManager_3847v3x7pw1km\pymanager.exe"
if not defined PYMANAGER_EXE if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.PythonManager_qbz5n2kfra8p0\pymanager.exe" set "PYMANAGER_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.PythonManager_qbz5n2kfra8p0\pymanager.exe"
if not defined PYMANAGER_EXE (
    echo.
    echo ERROR: Python was installed, but pymanager.exe could not be found.
    echo Sign out and back in to Windows, then run this installer again.
    goto :failed
)

echo.
echo [3/6] Installing Python 3.12...
"%PYMANAGER_EXE%" install 3.12
"%PYMANAGER_EXE%" exec -V:3.12 --version
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.12 was installed but did not pass verification.
    goto :failed
)

echo.
echo [4/6] Installing Git for Windows...
winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
set "PATH=%ProgramFiles%\Git\cmd;%LOCALAPPDATA%\Programs\Git\cmd;%PATH%"
for %%G in (git.exe) do set "GIT_EXE=%%~$PATH:G"
if not defined GIT_EXE (
    echo.
    echo ERROR: Git was installed, but git.exe could not be found.
    echo Restart Windows, then run this installer again.
    goto :failed
)

"%GIT_EXE%" lfs version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Git LFS is missing from the Git installation.
    goto :failed
)
"%GIT_EXE%" lfs install
if errorlevel 1 goto :failed

echo.
echo [5/6] Preparing the DefectTools repository...
if exist "%INSTALL_DIR%\.git\" goto :update_existing_checkout

set "UNEXPECTED_CONTENT="
for /F "delims=" %%F in ('dir /B /A "%INSTALL_DIR%" 2^>nul') do (
    if /I not "%%F"=="%INSTALLER_NAME%" set "UNEXPECTED_CONTENT=1"
)

if defined UNEXPECTED_CONTENT (
    echo.
    echo ERROR: The destination folder contains files other than this installer:
    echo   %INSTALL_DIR%
    echo.
    echo Create a new empty DefectTools folder, place this BAT inside it,
    echo and run it there. No existing files were changed.
    goto :failed
)

cd /D "%TEMP%"
del /F /Q "%INSTALL_DIR%\%INSTALLER_NAME%" >nul 2>&1
"%GIT_EXE%" clone --branch main --single-branch "%REPOSITORY_URL%" "%INSTALL_DIR%"
if errorlevel 1 (
    echo.
    echo ERROR: DefectTools could not be downloaded from GitHub.
    copy /Y "%~f0" "%INSTALL_DIR%\%INSTALLER_NAME%" >nul 2>&1
    goto :failed
)
goto :repository_ready

:update_existing_checkout
set "STATUS_FILE=%TEMP%\DefectToolsGitStatus_%RANDOM%_%RANDOM%.txt"
"%GIT_EXE%" -C "%INSTALL_DIR%" status --porcelain >"%STATUS_FILE%"
if errorlevel 1 goto :failed
for %%S in ("%STATUS_FILE%") do if %%~zS GTR 0 set "UNEXPECTED_CONTENT=1"
del /Q "%STATUS_FILE%" >nul 2>&1
if defined UNEXPECTED_CONTENT (
    echo.
    echo ERROR: This DefectTools checkout contains local changes.
    echo Commit or remove them before running the installer again.
    goto :failed
)
"%GIT_EXE%" -C "%INSTALL_DIR%" remote set-url origin "%REPOSITORY_URL%"
if errorlevel 1 goto :failed
"%GIT_EXE%" -C "%INSTALL_DIR%" fetch origin main
if errorlevel 1 goto :failed
"%GIT_EXE%" -C "%INSTALL_DIR%" checkout main
if errorlevel 1 goto :failed
"%GIT_EXE%" -C "%INSTALL_DIR%" branch --set-upstream-to=origin/main main >nul 2>&1
"%GIT_EXE%" -C "%INSTALL_DIR%" pull --ff-only
if errorlevel 1 goto :failed

:repository_ready
"%GIT_EXE%" -C "%INSTALL_DIR%" lfs pull
if errorlevel 1 goto :failed

echo.
echo [6/6] Verifying DefectTools...
set "PYTHONPATH=%INSTALL_DIR%\src"
py -3 --version
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.12 is installed, but the py command used by the
    echo DefectTools launchers is unavailable. Sign out and back in to
    echo Windows, then run this installer again.
    goto :failed
)
py -3 -c "import tkinter; import portable_pipe_tools; print('Python GUI and DefectTools imports: OK')"
if errorlevel 1 (
    echo.
    echo ERROR: DefectTools did not pass its Python import test.
    goto :failed
)

"%GIT_EXE%" -C "%INSTALL_DIR%" status --short --branch
echo.
echo ============================================================
echo  SUCCESS - DefectTools is ready!
echo ============================================================
echo.
echo Render Worker:
echo   %INSTALL_DIR%\tools\render_worker_gui.bat
echo.
echo Farm Render Manager:
echo   %INSTALL_DIR%\tools\farm_render_manager.bat
echo.
echo You can now close this window and double-click either tool.
echo.
pause
exit /b 0

:failed
echo.
echo ============================================================
echo  INSTALLATION STOPPED
echo ============================================================
echo Nothing in an occupied destination folder was overwritten.
echo Review the error above, then run the installer again.
echo.
pause
exit /b 1

:show_help
echo Place this BAT in a new, otherwise-empty DefectTools folder and run it.
echo It installs Python 3.12, Git, Git LFS, and the latest DefectTools main branch.
exit /b 0
