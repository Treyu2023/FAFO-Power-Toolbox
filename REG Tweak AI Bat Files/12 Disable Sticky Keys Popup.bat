@echo off
title Disable Sticky Keys Popup
echo Stopping Sticky Keys / Filter Keys prompts when Shift is held...

reg add "HKCU\Control Panel\Accessibility\StickyKeys" /v Flags /t REG_SZ /d 506 /f
reg add "HKCU\Control Panel\Accessibility\Keyboard Response" /v Flags /t REG_SZ /d 122 /f
reg add "HKCU\Control Panel\Accessibility\ToggleKeys" /v Flags /t REG_SZ /d 58 /f

echo Complete! Holding Shift will no longer pop the accessibility dialog.
pause
