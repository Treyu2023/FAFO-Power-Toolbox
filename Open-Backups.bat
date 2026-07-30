@echo off
:: This PC's FAFO Backups (device-local; also linked as Backups\ in this folder)
title Open FAFO Backups
cd /d "%~dp0"

set "DEV=%LOCALAPPDATA%\FAFO\Devices\%COMPUTERNAME%\Backups"
if exist "%~dp0Backups\" (
  start "" explorer.exe "%~dp0Backups"
  exit /b 0
)
if exist "%DEV%\" (
  start "" explorer.exe "%DEV%"
  exit /b 0
)

echo No Backups folder found yet. It is created when tools write backup data.
echo Expected: %DEV%
pause
