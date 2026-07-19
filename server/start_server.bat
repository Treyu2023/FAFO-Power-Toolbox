@echo off
title AI Toolbox Server
cd /d "%~dp0"

call "%~dp0..\Scripts\use-fafo-python.bat"
if errorlevel 1 (
  echo.
  echo  Python / .venv not ready. From toolbox root run:
  echo    INSTALL-PYTHON.bat
  echo.
  pause
  exit /b 1
)

echo.
echo  ========================================
echo   AI TOOLBOX SERVER
echo   Python: %FAFO_PYTHON%
echo   Keep this window open while using tools
echo  ========================================
echo.
echo  Tip: Prefer in-app "Start Server" (Launcher, Media Library,
echo        VSR, File Organizer) — one click, no menu needed.
echo.
echo  [1] Visible console (debug)
echo  [2] System tray (recommended)
echo  [3] Install autostart with Windows
echo.
choice /c 123 /n /m "Select mode: "
if errorlevel 3 goto autostart
if errorlevel 2 goto tray
if errorlevel 1 goto console

:tray
if exist "%FAFO_ROOT%\.venv\Scripts\pythonw.exe" (
  start /min "%FAFO_ROOT%\.venv\Scripts\pythonw.exe" "%~dp0tray_launcher.py"
) else (
  start /min "%FAFO_PYTHON%" "%~dp0tray_launcher.py"
)
echo Tray mode started. Check system tray for AI icon.
pause
exit /b

:autostart
call install_autostart.bat
exit /b

:console
"%FAFO_PYTHON%" aitoolbox_server.py
pause
