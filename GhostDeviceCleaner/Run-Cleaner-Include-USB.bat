@echo off
setlocal
cd /d "%~dp0"
set "PS5=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS5%" -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PS5%' -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','\"%~dp0Clear-GhostDevices.ps1\"','-IncludeUsb')"
exit /b 0