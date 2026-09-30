@echo off
:: Share Phone Launcher on this Wi-Fi. Static HTML only — not the loopback API.
setlocal EnableExtensions
cd /d "%~dp0"
title FAFO Phone LAN
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Start-PhoneLan.ps1" -ToolboxRoot "%~dp0."
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" (
  echo.
  echo Phone LAN failed ^(exit %EC%^). See messages above.
  pause
)
endlocal & exit /b %EC%
