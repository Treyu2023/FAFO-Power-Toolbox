@echo off
title Enable Long Paths
echo Enabling Win32 Long Paths for deep directories...

reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f

echo.
echo Complete! Please reboot your PC for this to take full effect.
pause