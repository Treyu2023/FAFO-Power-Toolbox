@echo off
:: One-click thin shell: auto setup if needed → start server → Chrome --app (never Edge).
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Start-FAFOShell.ps1" -ToolboxRoot "%~dp0."
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo Launch failed ^(exit %EC%^). See messages above.
  pause
)
endlocal & exit /b %EC%
