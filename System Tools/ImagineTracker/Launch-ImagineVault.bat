@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if exist "%~dp0Launch-ImagineVault.vbs" (
  start "" wscript.exe //B "%~dp0Launch-ImagineVault.vbs"
  exit /b 0
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Launch-ImagineVault.ps1"
exit /b 0
