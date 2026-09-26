@echo off
cd /d "%~dp0\.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0..\Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0.." -TrayOnly -Quiet
exit /b 0
