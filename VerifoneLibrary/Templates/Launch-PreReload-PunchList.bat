@echo off
REM Launcher copy kept next to the MASTER spreadsheet.
REM Working copies are always created under ..\Working-PunchLists\
setlocal
cd /d "%~dp0.."
title CITGO VAPS Pre-Reload Punch List

echo.
echo  Creating a WORKING copy of the Pre-Reload Punch List...
echo  Master in Templates\ is never modified.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\Launch-PreReload-PunchList.ps1" %*
set ERR=%ERRORLEVEL%
if %ERR% neq 0 (
  echo.
  echo  Launch failed with code %ERR%.
  pause
  exit /b %ERR%
)
exit /b 0
