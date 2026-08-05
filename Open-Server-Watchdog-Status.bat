@echo off
set "HTML=%LOCALAPPDATA%\FAFO\Devices\%COMPUTERNAME%\Reports\server-watchdog-status.html"
if not exist "%HTML%" (
  echo Status page not generated yet — starting one-shot check...
  cd /d "%~dp0"
  if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0server\server_watchdog.py" --once
  )
)
if exist "%HTML%" (
  start "" "%HTML%"
) else (
  echo Could not create status page. Run Start-Server-Watchdog.bat first.
  pause
)
