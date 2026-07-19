@echo off
title Install AI Toolbox Autostart
cd /d "%~dp0"

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LINK=%STARTUP%\AI Toolbox Server.lnk"
set "TARGET=%~dp0start_tray.bat"
set "WORKDIR=%~dp0"

powershell -NoProfile -Command ^
  "$s = New-Object -ComObject WScript.Shell; ^
   $l = $s.CreateShortcut('%LINK%'); ^
   $l.TargetPath = '%TARGET%'; ^
   $l.WorkingDirectory = '%WORKDIR%'; ^
   $l.WindowStyle = 7; ^
   $l.Description = 'AI Toolbox Server'; ^
   $l.Save()"

echo.
echo  Autostart installed:
echo  %LINK%
echo.
echo  Server will start minimized with Windows (system tray).
echo  To remove: delete the shortcut from Startup folder.
pause