@echo off
title AI HTML Toolbox — Install Python environment
cd /d "%~dp0"

echo.
echo  ================================================
echo   AI HTML TOOLBOX — Local Python setup
echo  ================================================
echo.
echo  This creates a private virtualenv at:
echo    %~dp0.venv\
echo.
echo  Packages install ONLY into .venv (not global Python).
echo  Requires Python 3.10+  (3.12 recommended)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Install-PythonEnvironment.ps1" -ToolboxRoot "%~dp0."
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo  Setup failed with exit code %ERR%.
  pause
  exit /b %ERR%
)

echo  Next: double-click "Install FAFO Toolbox.bat" once, then use Desktop shortcuts.
echo.
pause
exit /b 0
