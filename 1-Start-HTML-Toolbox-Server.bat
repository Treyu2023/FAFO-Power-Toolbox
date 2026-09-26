@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -NoFafoMeta -Force
exit /b %ERRORLEVEL%
