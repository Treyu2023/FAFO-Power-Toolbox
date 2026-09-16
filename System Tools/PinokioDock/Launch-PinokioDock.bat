@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0Launch-PinokioDock.vbs" (
  start "" wscript.exe //B "%~dp0Launch-PinokioDock.vbs"
  exit /b 0
)
start "" /MIN powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0PinokioDock.ps1"
exit /b 0
