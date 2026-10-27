@echo off
:: Opens the standalone FAFO Auto Tech repo (C:\_Git\repos\html\FAFO-Auto-Tech).
:: Desktop shortcut: FAFO Auto Technician. Icon: Change-FAFO-Auto-Tech-Icon.bat
setlocal EnableExtensions
cd /d "%~dp0"
title FAFO Auto Technician
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Launch-FAFO-Auto-Tech.ps1"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo FAFO Auto Technician did not start ^(exit %EC%^).
  pause
)
endlocal & exit /b %EC%
