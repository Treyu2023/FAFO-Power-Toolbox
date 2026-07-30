@echo off
:: Back-compat name: starts companions hidden + tray (same as "Start Servers.bat")
title AI Toolbox — Starting servers (background)
cd /d "%~dp0"

if not exist "%~dp0Scripts\Start-FAFOServers.ps1" (
  echo Missing Scripts\Start-FAFOServers.ps1
  echo Run INSTALL-PYTHON.bat / setup first.
  pause
  exit /b 1
)

echo.
echo  Starting FAFO servers in the background...
echo    S1 HTML Toolbox Server     : http://127.0.0.87:18765
echo       (Media / Verifone / System Tools / File tools)
echo    S2 FAFO Local Media Tagger : http://127.0.0.1:8765
echo       (Chrome FAFO Local Media extension tags/ratings)
echo  No console windows - tray / Desktop Start Servers /
echo  0-Start-ALL / 1-Start-S1 / 2-Start-S2 / Stop-ALL-Servers.bat
echo.

echo [%date% %time%] START SERVER.bat (hidden multi-server)>> "%~dp0server\startup.log"

powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%~dp0." -Quiet
set "EC=%ERRORLEVEL%"

if not "%EC%"=="0" (
  echo  Start helper exited with code %EC%.
  echo  Try: INSTALL-PYTHON.bat then this again.
  pause
  exit /b %EC%
)

echo  Done. Look for the FAFO tray icon ^(or Start Menu / Desktop shortcuts^).
timeout /t 2 /nobreak >nul
exit /b 0
