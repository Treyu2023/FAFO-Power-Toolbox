@echo off
title Disable Aero Shake
echo Disabling shake-to-minimize on window title bars...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v DisallowShaking /t REG_DWORD /d 1 /f

echo Complete! Shaking a window will no longer minimize the others.
pause
