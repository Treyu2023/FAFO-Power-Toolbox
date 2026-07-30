@echo off
:: S1 — HTML Toolbox Server (127.0.0.87:18765)
:: Powers: Media Library, VSR, File tools, Verifone, System Tools, Launcher
title S1 HTML Toolbox Server
cd /d "%~dp0"

if not exist "%~dp0Scripts\Start-FAFOServers.ps1" (
  echo Missing Scripts\Start-FAFOServers.ps1
  pause
  exit /b 1
)

echo.
echo  Starting S1 HTML Toolbox Server only...
echo    Endpoint: http://127.0.0.87:18765
echo    Powers:   HTML tools / Verifone / media / system tools
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -NoFafoMeta -Quiet
exit /b %ERRORLEVEL%
