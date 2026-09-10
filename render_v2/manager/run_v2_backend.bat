@echo off
setlocal
cd /d "%~dp0cloudflare\defect-farm-api"
call node_modules\.bin\wrangler.cmd d1 migrations apply defect-farm-v2-local --local --persist-to "..\..\LocalSaveFiles\v2-backend"
if errorlevel 1 exit /b 1
call node_modules\.bin\wrangler.cmd dev --local --ip 127.0.0.1 --port 8795 --persist-to "..\..\LocalSaveFiles\v2-backend" --var ENVIRONMENT:v2-local --var SUBMIT_TOKEN:local-submit-token-for-tests --var WORKER_TOKEN:local-worker-token-for-tests --var MANAGER_TOKEN:local-manager-token-for-tests --var VIEWER_TOKEN:local-viewer-token-for-tests
endlocal
