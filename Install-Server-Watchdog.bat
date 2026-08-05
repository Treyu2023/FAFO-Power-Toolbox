@echo off
:: Install FAFO Server Watchdog as Scheduled Tasks (logon + 5-min poll)
title Install FAFO Server Watchdog
cd /d "%~dp0"

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\python.exe" (
  set "PY=C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\python.exe"
)
if not defined PY (
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
start "FAFO-Watchdog" /MIN "%~dp0.venv\Scripts\pythonw.exe" "%~dp0server\server_watchdog.py" 2>nul
if errorlevel 1 start "FAFO-Watchdog" /MIN "%PY%" "%~dp0server\server_watchdog.py"

echo.
echo Done.
echo  - Tasks: FAFO-Server-Watchdog , FAFO-Server-Watchdog-Poll
echo  - Report: %%LOCALAPPDATA%%\FAFO\Devices\%COMPUTERNAME%\Reports\server-watchdog-status.html
echo  - Log:    %%LOCALAPPDATA%%\FAFO\Devices\%COMPUTERNAME%\Logs\server-watchdog.log
echo  - Attention flag: ...\Reports\ATTENTION-SERVERS.txt  (only when critical)
echo.
pause
