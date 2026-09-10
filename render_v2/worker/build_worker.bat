@echo off
powershell -NoProfile -File "%~dp0tools\build_worker.ps1"
exit /b %errorlevel%
