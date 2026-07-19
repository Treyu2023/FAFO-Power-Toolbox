@echo off
title AI Toolbox Server (Console)
cd /d "%~dp0"

call "%~dp0Scripts\use-fafo-python.bat"
if errorlevel 1 (
  echo  Run INSTALL-PYTHON.bat first to create .venv
  pause
  exit /b 1
)

cd /d "%~dp0server"
echo.
echo  Using: %FAFO_PYTHON%
echo  Endpoint: http://127.0.0.87:18765
echo.
"%FAFO_PYTHON%" aitoolbox_server.py
pause
