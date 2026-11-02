@echo off
:: Opens FAFO Auto Mechanic (C:\_Git\repos\html\FAFO-Auto-Tech).
:: Desktop shortcut: FAFO Auto Mechanic. Icon: Change-FAFO-Auto-Tech-Icon.bat
setlocal EnableExtensions
cd /d "%~dp0"
title FAFO Auto Mechanic
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Launch-FAFO-Auto-Tech.ps1"
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo FAFO Auto Mechanic did not start ^(exit %EC%^).
  pause
)
endlocal & exit /b %EC%
