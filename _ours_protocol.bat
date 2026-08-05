@echo off
REM Custom protocol handler for aitoolbox:// ΓÇö no browser downloads.
REM Registered by SETUP (run once).bat as:
REM   HKCU\Software\Classes\aitoolbox\shell\open\command
REM
REM Supported URLs:
REM   aitoolbox://start          Start companions hidden + tray (no install folder needed)
REM   aitoolbox://restart        Stop+start companions (relaunch)
REM   aitoolbox://tray           Ensure system tray helper only
REM   aitoolbox://console        Start server with visible console
REM   aitoolbox://folder         Open toolbox root in Explorer
REM   aitoolbox://setup          Run one-time setup
REM   aitoolbox://launch         One-click: setup if needed + server + Chrome shell
REM   aitoolbox://diagnostics    Full system diagnostics + pack report library
REM   aitoolbox://pack-reports   Rebuild catalog.js / logs-data.js only
REM   aitoolbox://ghost          Ghost Device Cleaner (elevated UAC + picker)

setlocal EnableExtensions
cd /d "%~dp0.."

set "ACTION=start"
set "RAW=%~1"
if defined RAW (
  REM crude contains checks (URLs are ASCII) ΓÇö more specific actions first
  echo %RAW%| findstr /I /C:"ghost" >nul && set "ACTION=ghost"
  echo %RAW%| findstr /I /C:"console" >nul && set "ACTION=console"
  echo %RAW%| findstr /I /C:"folder" >nul && set "ACTION=folder"
  echo %RAW%| findstr /I /C:"open" >nul && set "ACTION=folder"
  echo %RAW%| findstr /I /C:"setup" >nul && set "ACTION=setup"
  echo %RAW%| findstr /I /C:"launch" >nul && set "ACTION=launch"
  echo %RAW%| findstr /I /C:"diagnostics" >nul && set "ACTION=diagnostics"
  echo %RAW%| findstr /I /C:"pack-reports" >nul && set "ACTION=pack"
  echo %RAW%| findstr /I /C:"packreports" >nul && set "ACTION=pack"
  echo %RAW%| findstr /I /C:"restart" >nul && set "ACTION=restart"
  echo %RAW%| findstr /I /C:"tray" >nul && set "ACTION=tray"
  echo %RAW%| findstr /I /C:"start" >nul && if /I not "%ACTION%"=="console" if /I not "%ACTION%"=="folder" if /I not "%ACTION%"=="setup" if /I not "%ACTION%"=="launch" if /I not "%ACTION%"=="diagnostics" if /I not "%ACTION%"=="pack" if /I not "%ACTION%"=="restart" if /I not "%ACTION%"=="tray" if /I not "%ACTION%"=="ghost" set "ACTION=start"
)

if /I "%ACTION%"=="ghost" goto do_ghost
if /I "%ACTION%"=="folder" goto do_folder
if /I "%ACTION%"=="setup" goto do_setup
if /I "%ACTION%"=="launch" goto do_launch
if /I "%ACTION%"=="console" goto do_console
if /I "%ACTION%"=="diagnostics" goto do_diagnostics
if /I "%ACTION%"=="pack" goto do_pack
if /I "%ACTION%"=="restart" goto do_restart
if /I "%ACTION%"=="tray" goto do_tray
goto do_start

:do_ghost
REM Elevated Ghost Device Cleaner ΓÇö UAC then PowerShell picker
if exist "%cd%\GhostDeviceCleaner\Run-Cleaner-Elevated.bat" (
  start "" "%cd%\GhostDeviceCleaner\Run-Cleaner-Elevated.bat"
  exit /b 0
)
if exist "%cd%\GhostDeviceCleaner\Clear-GhostDevices.ps1" (
  start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-NoExit','-File','\"%cd%\GhostDeviceCleaner\Clear-GhostDevices.ps1\"')"
  exit /b 0
)
start "" explorer.exe "%cd%\GhostDeviceCleaner"
exit /b 1

:do_folder
start "" explorer.exe "%cd%"
exit /b 0

:do_setup
if exist "%cd%\Scripts\Install-FAFOToolbox.ps1" (
  start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%cd%\Scripts\Install-FAFOToolbox.ps1" -ToolboxRoot "%cd%"
) else (
  start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%cd%\Scripts\Complete-FAFOSetup.ps1" -ToolboxRoot "%cd%"
)
exit /b 0

:do_launch
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%cd%\Scripts\Launch-FAFOToolbox.ps1" -ToolboxRoot "%cd%"
exit /b 0

:do_console
if exist "%cd%\START SERVER (Console).bat" (
  start "" "%cd%\START SERVER (Console).bat"
) else (
  call "%~dp0start_console_now.bat" 2>nul
  if errorlevel 1 start "" cmd /k "cd /d "%cd%\server" && call ..\Scripts\use-fafo-python.bat && "%FAFO_PYTHON%" aitoolbox_server.py"
)
exit /b 0

:do_diagnostics
start "FAFO Diagnostics" cmd /c "cd /d "%cd%" && powershell -NoProfile -ExecutionPolicy Bypass -File "%cd%\Scripts\Invoke-FAFOSystemDiagnostics.ps1" -ToolboxRoot "%cd%" -OpenViewer & pause"
exit /b 0

:do_pack
start "FAFO Pack Reports" cmd /c "cd /d "%cd%" && powershell -NoProfile -ExecutionPolicy Bypass -File "%cd%\System Tools\PC Reports and Log Viewer\_pack_logs.ps1" -ToolboxRoot "%cd%" & pause"
exit /b 0

:do_restart
REM Full restart of companions (hidden) ΓÇö stops listeners then starts again
if exist "%cd%\Scripts\Start-FAFOServers.ps1" (
  start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%cd%\Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%cd%" -Restart -Quiet
  exit /b 0
)
goto do_start

:do_tray
if exist "%cd%\Scripts\Start-FAFOServers.ps1" (
  start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%cd%\Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%cd%" -TrayOnly -Quiet
  exit /b 0
)
if exist "%cd%\server\start_tray.bat" (
  start "" /b "%cd%\server\start_tray.bat"
)
exit /b 0

:do_start
REM Multi-server hidden + tray ΓÇö no install-folder navigation required
if exist "%cd%\Scripts\Start-FAFOServers.ps1" (
  start "" /b powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%cd%\Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%cd%" -Quiet
  exit /b 0
)
if exist "%cd%\Start Servers.bat" (
  start "" /b "%cd%\Start Servers.bat"
  exit /b 0
)
REM Fallback: pythonw hidden
call "%~dp0..\Scripts\use-fafo-python.bat"
if errorlevel 1 exit /b 1
if exist "%FAFO_ROOT%\.venv\Scripts\pythonw.exe" (
  start "" /b "%FAFO_ROOT%\.venv\Scripts\pythonw.exe" "%~dp0aitoolbox_server.py"
) else (
  start "" /b "%FAFO_PYTHON%" "%~dp0aitoolbox_server.py"
)
exit /b 0
