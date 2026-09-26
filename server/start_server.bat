@echo off
cd /d "%~dp0\.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0.." -Force
exit /b %ERRORLEVEL%
