@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -Force -Quiet
exit /b %ERRORLEVEL%
