@echo off
:: Compatibility alias — full installer is "Install FAFO Toolbox.bat"
title AI Toolbox Setup
cd /d "%~dp0"

if exist "%~dp0Install FAFO Toolbox.bat" (
  call "%~dp0Install FAFO Toolbox.bat"
  exit /b %ERRORLEVEL%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Install-FAFOToolbox.ps1" -ToolboxRoot "%~dp0."
set "EC=%ERRORLEVEL%"
echo.
pause
exit /b %EC%
