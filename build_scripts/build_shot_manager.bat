@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0.."
set "PYTHON_VERSION=3.12"
set "VENV_DIR=%REPO_ROOT%\.venv_build"
set "BUILD_DIR=%REPO_ROOT%\build"
set "DIST_DIR=%REPO_ROOT%\dist"
set "LAUNCHER_PATH=%BUILD_DIR%\shot_manager_launcher.py"

pushd "%REPO_ROOT%" || exit /b 1

echo.
echo ========================================
echo Building ShotManager standalone app
echo Repo: %CD%
echo Python: %PYTHON_VERSION%
echo ========================================
echo.

py -%PYTHON_VERSION% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python %PYTHON_VERSION% was not found by the Windows py launcher.
    echo.
    echo Detected Python installs:
    py -0p
    echo.
    echo Install Python %PYTHON_VERSION% or edit PYTHON_VERSION in this script.
    popd
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating build virtual environment...
    py -%PYTHON_VERSION% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :fail
) else (
    echo Using existing build virtual environment.
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo.
echo Installing build dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install pyinstaller
if errorlevel 1 goto :fail
python -m pip install -e .
if errorlevel 1 goto :fail

echo.
echo Cleaning previous build output...
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%\ShotManager" rmdir /s /q "%DIST_DIR%\ShotManager"
mkdir "%BUILD_DIR%"
if errorlevel 1 goto :fail

> "%LAUNCHER_PATH%" echo from portable_pipe_tools.show_manager.shot_manager_core import main
>> "%LAUNCHER_PATH%" echo.
>> "%LAUNCHER_PATH%" echo main()

echo.
echo Running PyInstaller...
pyinstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --windowed ^
  --name ShotManager ^
  --paths "%REPO_ROOT%\src" ^
  --workpath "%BUILD_DIR%" ^
  --specpath "%BUILD_DIR%" ^
  --distpath "%DIST_DIR%" ^
  "%LAUNCHER_PATH%"
if errorlevel 1 goto :fail

echo.
echo ========================================
echo Build complete.
echo Run:
echo   "%DIST_DIR%\ShotManager\ShotManager.exe"
echo.
echo Zip this whole folder for artists:
echo   "%DIST_DIR%\ShotManager"
echo ========================================
echo.

popd
exit /b 0

:fail
echo.
echo ERROR: ShotManager build failed.
echo.
popd
exit /b 1
