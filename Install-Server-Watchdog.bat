@echo off
title Install FAFO Server Watchdog
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo No .venv Python found. Run INSTALL-PYTHON.bat first.
  pause
  exit /b 1
)
echo Installing Scheduled Tasks: FAFO-Server-Watchdog (+ 5-min poll)...
"%PY%" "%~dp0server\server_watchdog.py" --install-task
if errorlevel 1 (
  echo Install reported an error.
  pause
  exit /b 1
)
echo.
echo Starting watchdog now...
if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "FAFO-Watchdog" /MIN "%~dp0.venv\Scripts\pythonw.exe" "%~dp0server\server_watchdog.py"
) else (
  start "FAFO-Watchdog" /MIN "%PY%" "%~dp0server\server_watchdog.py"
)
echo Done. Report: %%LOCALAPPDATA%%\FAFO\Devices\%COMPUTERNAME%\Reports\server-watchdog-status.html
pause
