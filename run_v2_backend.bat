@echo off
setlocal
pushd "%~dp0render_v2\manager\cloudflare\defect-farm-api"
if not exist "node_modules\.bin\wrangler.cmd" (
    call npm ci
    if errorlevel 1 (
        popd
        exit /b 1
    )
)
popd
call "%~dp0render_v2\manager\run_v2_backend.bat" %*
set "v2BackendExit=%ERRORLEVEL%"
endlocal & exit /b %v2BackendExit%
