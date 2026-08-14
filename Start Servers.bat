@echo off
:: Hidden multi-server start + system tray (no install-folder hunting).
:: Double-click from Desktop shortcut, Start Menu, or pin to taskbar.
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0Scripts\Start-FAFOServers.ps1" (
  echo Missing Scripts\Start-FAFOServers.ps1
  pause
  exit /b 1
)

REM -Force: user asked for Start All — start S1+S2 now (S2 even without Chrome)
REM WindowStyle Hidden — no black console for users to close by mistake
start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -Force -Quiet

REM Tiny feedback without leaving a stuck window (optional toast-style flash)
timeout /t 1 /nobreak >nul
exit /b 0
