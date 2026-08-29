@echo off
title Hide Widgets / News Button
echo Hiding the Widgets / News and Interests taskbar button...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v TaskbarDa /t REG_DWORD /d 0 /f

taskkill /f /im explorer.exe
start explorer.exe
echo Complete! Widgets button is hidden.
pause
