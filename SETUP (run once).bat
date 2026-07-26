@echo off
title AI Toolbox Setup
cd /d "%~dp0"

echo.
echo  AI HTML TOOLBOX — One-time setup
echo  =================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Complete-FAFOSetup.ps1" -ToolboxRoot "%~dp0."
set "EC=%ERRORLEVEL%"
echo.
if "%EC%"=="0" (
  echo  Setup finished successfully.
) else (
  echo  Setup finished with issues ^(exit %EC%^). Review messages above.
)
echo.
pause
endlocal & exit /b %EC%
