@echo off
title Show File Extensions and Hidden Files
echo Forcing Windows to show file extensions and hidden files...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v HideFileExt /t REG_DWORD /d 0 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v Hidden /t REG_DWORD /d 1 /f

taskkill /f /im explorer.exe
start explorer.exe
echo Complete! File extensions and hidden files are now visible.
pause