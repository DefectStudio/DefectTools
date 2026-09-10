@echo off
setlocal
set "PYTHONPATH=%~dp0render_v2\manager\src"
pushd "%~dp0render_v2\manager"
py -3 -m unittest discover -s tests -p "test_*.py"
set "v2ManagerTestExit=%ERRORLEVEL%"
popd
call "%~dp0render_v2\worker\test_worker.bat" --no-pause
set "v2WorkerTestExit=%ERRORLEVEL%"
set "v2TestExit=0"
if not "%v2ManagerTestExit%"=="0" set "v2TestExit=1"
if not "%v2WorkerTestExit%"=="0" set "v2TestExit=1"
if /I not "%~1"=="--no-pause" pause
endlocal & exit /b %v2TestExit%
