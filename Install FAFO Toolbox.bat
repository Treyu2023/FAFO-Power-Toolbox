@echo off
title AI HTML Toolbox - Installer
cd /d "%~dp0"

echo.
echo  Opening installer...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Install-FAFOToolbox.ps1" -ToolboxRoot "%~dp0."
set "EC=%ERRORLEVEL%"

echo.
if "%EC%"=="0" (
  echo  Done. You can close this window.
) else (
  echo  Installer finished with issues ^(exit %EC%^). Scroll up for details.
)
echo.
pause
exit /b %EC%
