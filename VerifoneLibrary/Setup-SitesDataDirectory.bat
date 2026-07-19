@echo off
setlocal
cd /d "%~dp0"
title FAFO Verifone - Setup local site data directory

echo.
echo  Choose where Customer\Site backups live on THIS machine.
echo  A junction VerifoneLibrary\Sites will point there (mklink /J).
echo  Site XML is local-only and will NOT be pushed to GitHub.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-SitesDataDirectory.ps1" %*
set ERR=%ERRORLEVEL%
if %ERR% neq 0 (
  echo.
  echo  Setup failed with code %ERR%.
  pause
  exit /b %ERR%
)
echo.
pause
exit /b 0
