@echo off
title Show Seconds on Taskbar Clock
echo Enabling seconds on the notification-area clock...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v ShowSecondsInSystemClock /t REG_DWORD /d 1 /f

taskkill /f /im explorer.exe
start explorer.exe
echo Complete! The clock now shows seconds.
pause
