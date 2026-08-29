@echo off
title Enable End Task on Taskbar
echo Adding End task to app icons on the taskbar...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v TaskbarEndTask /t REG_DWORD /d 1 /f

echo Complete! Right-click a running app on the taskbar to End task.
echo (Windows 11 22H2+). Sign out if it does not appear yet.
pause
