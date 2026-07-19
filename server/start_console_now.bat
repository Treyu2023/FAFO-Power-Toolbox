@echo off
cd /d "%~dp0"
title AI Toolbox Server
call "%~dp0..\Scripts\use-fafo-python.bat"
if errorlevel 1 (
  echo Run INSTALL-PYTHON.bat from the toolbox root first.
  pause
  exit /b 1
)
echo [%date% %time%] Starting console server...>> startup.log
echo Using %FAFO_PYTHON%
"%FAFO_PYTHON%" "%~dp0aitoolbox_server.py"
pause
