@echo off
:: S2 — FAFO Local Media Tagger (127.0.0.1:8765)
:: Powers: Chrome FAFO Local Media extension (tags, ratings, pairs, Explorer sync)
title S2 FAFO Local Media Tagger
cd /d "%~dp0"

if not exist "%~dp0Scripts\Start-FAFOServers.ps1" (
  echo Missing Scripts\Start-FAFOServers.ps1
  pause
  exit /b 1
)

echo.
echo  Starting S2 FAFO Local Media Tagger only...
echo    Endpoint: http://127.0.0.1:8765
echo    Powers:   FAFO Local Media Chrome extension
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -NoToolbox -Quiet
exit /b %ERRORLEVEL%
