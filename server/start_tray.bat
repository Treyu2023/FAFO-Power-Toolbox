@echo off
cd /d "%~dp0"
call "%~dp0..\Scripts\use-fafo-python.bat"
if errorlevel 1 (
  echo Run INSTALL-PYTHON.bat from the toolbox root first.
  pause
  exit /b 1
)
if exist "%FAFO_ROOT%\.venv\Scripts\pythonw.exe" (
  start /min "%FAFO_ROOT%\.venv\Scripts\pythonw.exe" "%~dp0tray_launcher.py"
) else (
  start /min "%FAFO_PYTHON%" "%~dp0tray_launcher.py"
)
