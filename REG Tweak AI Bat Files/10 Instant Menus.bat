@echo off
title Instant Menus
echo Setting menu show delay to 0...

reg add "HKCU\Control Panel\Desktop" /v MenuShowDelay /t REG_SZ /d 0 /f

taskkill /f /im explorer.exe
start explorer.exe
echo Complete! Cascading menus open immediately.
pause
