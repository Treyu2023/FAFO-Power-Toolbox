@echo off
title Explorer Opens to This PC
echo Setting File Explorer to open on This PC...

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" /v LaunchTo /t REG_DWORD /d 1 /f

echo Complete! New Explorer windows start on This PC.
pause
