@echo off
cd /d "%~dp0\.."
start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%CD%\Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%CD%" -NoFafoMeta -Force -Quiet
start "" "%~dp0LAN Task Manager.html"
exit /b 0
