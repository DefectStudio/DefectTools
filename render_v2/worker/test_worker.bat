@echo off
setlocal
set "PYTHONPATH=%~dp0src"
py -3 -m unittest discover -s "%~dp0tests" -p "test_*.py" -v
set "WORKER_TEST_EXIT_CODE=%ERRORLEVEL%"
echo.
if "%WORKER_TEST_EXIT_CODE%"=="0" (
    echo Render Worker tests passed.
) else (
    echo Render Worker tests failed. See the output above.
)
if /I not "%~1"=="--no-pause" pause
endlocal & exit /b %WORKER_TEST_EXIT_CODE%
