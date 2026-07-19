@echo off
setlocal
cd /d "%~dp0"
start "" mshta.exe "%~dp0Clear-GhostDevices.html"
exit /b 0