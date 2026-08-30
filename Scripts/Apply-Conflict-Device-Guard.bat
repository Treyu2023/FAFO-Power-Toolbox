@echo off
:: Re-apply PAN / AURA LED / Sonic Studio disable. Leaves L-Connect + NZXT CAM + USB-BT500.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Set-FAFOConflictDevices.ps1" -InstallGuard
pause
