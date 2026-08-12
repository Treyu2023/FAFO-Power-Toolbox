@echo off
:: S2 — Ultimate Tab / Local Media Tagger (127.0.0.1:8765)
:: Lifecycle: normally starts with Google Chrome. This bat is a manual override.
title S2 Ultimate Tab Tagger
cd /d "%~dp0"

if not exist "%~dp0Scripts\Start-FAFOServers.ps1" (
  echo Missing Scripts\Start-FAFOServers.ps1
  pause
  exit /b 1
)

echo.
echo  Starting S2 Ultimate Tab / Local Media Tagger only...
echo    Endpoint: http://127.0.0.1:8765
echo    (Normally auto-starts when Chrome is running)
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -NoToolbox -Restart -Quiet
exit /b %ERRORLEVEL%
