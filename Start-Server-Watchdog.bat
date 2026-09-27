@echo off
cd /d "%~dp0"
set "PY=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo No .venv Python found. Run INSTALL-PYTHON.bat first.
  pause
  exit /b 1
)
echo Starting FAFO Server Watchdog...
start "FAFO-Watchdog" /MIN "%PY%" "%~dp0server\server_watchdog.py"
exit /b 0
