@echo off
cd /d "%~dp0"
title AI Toolbox Server (Console)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -Console -NoFafoMeta
exit /b %ERRORLEVEL%
