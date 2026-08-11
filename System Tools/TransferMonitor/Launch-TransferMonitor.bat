@echo off
REM Launch Transfer Monitor with NO visible PowerShell console (tray + GUI only).
setlocal EnableExtensions
cd /d "%~dp0"

if exist "%~dp0Launch-TransferMonitor.vbs" (
  start "" wscript.exe //B "%~dp0Launch-TransferMonitor.vbs"
  exit /b 0
)

REM Fallback: hidden PowerShell (may briefly flash on some systems)
start "" /MIN powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0TransferMonitor.ps1"
exit /b 0
