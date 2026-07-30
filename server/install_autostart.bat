@echo off
title Install FAFO Toolbox Autostart
cd /d "%~dp0.."

set "ROOT=%cd%"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LINK=%STARTUP%\FAFO Toolbox Servers.lnk"
set "PS1=%ROOT%\Scripts\Start-FAFOServers.ps1"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%PS1%" (
  echo Missing Start-FAFOServers.ps1
  pause
  exit /b 1
)

REM Remove legacy tray-only shortcut if present
if exist "%STARTUP%\AI Toolbox Server.lnk" del /f /q "%STARTUP%\AI Toolbox Server.lnk" >nul 2>&1

powershell -NoProfile -Command ^
  "$s = New-Object -ComObject WScript.Shell; ^
   $l = $s.CreateShortcut('%LINK%'); ^
   $l.TargetPath = '%POWERSHELL%'; ^
   $l.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""%PS1%"" -ToolboxRoot ""%ROOT%"" -Quiet'; ^
   $l.WorkingDirectory = '%ROOT%'; ^
   $l.WindowStyle = 7; ^
   $l.Description = 'FAFO Toolbox companion servers (toolbox + FAFO tagging)'; ^
   $l.Save()"

echo.
echo  Autostart installed (servers with Windows):
echo  %LINK%
echo.
echo  Starts toolbox (Verifone/media) + FAFO Local Tab tagging when configured.
echo  Prefer Launcher toggles: "Launch with Windows" for servers and/or app.
echo  To remove: delete the shortcut from the Startup folder, or use the Launcher.
pause