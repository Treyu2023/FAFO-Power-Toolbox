@echo off
title Verbose Startup / Shutdown Status
echo Enabling verbose boot and shutdown messages (needs Administrator)...

reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v VerboseStatus /t REG_DWORD /d 1 /f
if errorlevel 1 (
  echo Failed — re-run this script as Administrator.
  pause
  exit /b 1
)

echo Complete! Boot and shutdown will name the driver / service in progress.
pause
