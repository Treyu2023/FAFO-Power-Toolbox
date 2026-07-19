@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Desktop-Shortcut.ps1" -StartMenu
echo.
pause
