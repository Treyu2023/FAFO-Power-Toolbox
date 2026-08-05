@echo off
:: FAFO S1+S2 Server Watchdog — auto-heal + attention reports
title FAFO Server Watchdog
cd /d "%~dp0"

set "PY="
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PY=%~dp0.venv\Scripts\pythonw.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\pythonw.exe" (
  set "PY=C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\pythonw.exe"
)
if not defined PY (
  echo No .venv Python found. Run INSTALL-PYTHON.bat first.
  pause
  exit /b 1
)

echo Starting FAFO Server Watchdog...
echo   S1 http://127.0.0.87:18765
echo   S2 http://127.0.0.1:8765
echo   Status: %%LOCALAPPDATA%%\FAFO\Devices\%COMPUTERNAME%\Reports\server-watchdog-status.html
echo.

start "FAFO-Watchdog" /MIN "%PY%" "%~dp0server\server_watchdog.py"
timeout /t 2 /nobreak >nul
echo Watchdog launched (minimized). It will keep S1/S2 up and write attention reports.
exit /b 0
