@echo off
title AI Toolbox Server
cd /d "%~dp0"

echo.
echo  ========================================
echo   AI TOOLBOX SERVER
echo   Keep this window open while using tools
echo  ========================================
echo.

python -m pip install -q -r requirements.txt 2>nul
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
start /min pythonw tray_launcher.py
echo Tray mode started. Check system tray for AI icon.
pause
exit /b
:autostart
call install_autostart.bat
exit /b
:console
python aitoolbox_server.py
pause