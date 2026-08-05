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
REM   aitoolbox://watchdog       Start S1/S2 server watchdog
REM   aitoolbox://watchdog-status Open watchdog status HTML
REM   aitoolbox://watchdog-install Install watchdog Startup + poll task
REM   aitoolbox://watchdog-folder  Explorer select Start-Server-Watchdog.bat

setlocal EnableExtensions
cd /d "%~dp0.."

set "ACTION=start"
set "RAW=%~1"
if defined RAW (
  REM crude contains checks (URLs are ASCII) ΓÇö more specific actions first
  echo %RAW%| findstr /I /C:"watchdog-status" >nul && set "ACTION=watchdog-status"
  echo %RAW%| findstr /I /C:"watchdog-install" >nul && set "ACTION=watchdog-install"
  echo %RAW%| findstr /I /C:"watchdog-folder" >nul && set "ACTION=watchdog-folder"
  echo %RAW%| findstr /I /C:"watchdog" >nul && if /I not "%ACTION%"=="watchdog-status" if /I not "%ACTION%"=="watchdog-install" if /I not "%ACTION%"=="watchdog-folder" set "ACTION=watchdog"
  echo %RAW%| findstr /I /C:"console" >nul && set "ACTION=console"
  echo %RAW%| findstr /I /C:"folder" >nul && if /I not "%ACTION%"=="watchdog-folder" set "ACTION=folder"
  echo %RAW%| findstr /I /C:"open" >nul && if /I not "%ACTION%"=="watchdog-folder" if /I not "%ACTION%"=="watchdog-status" set "ACTION=folder"
  echo %RAW%| findstr /I /C:"setup" >nul && set "ACTION=setup"
  echo %RAW%| findstr /I /C:"launch" >nul && set "ACTION=launch"
  echo %RAW%| findstr /I /C:"diagnostics" >nul && set "ACTION=diagnostics"
  echo %RAW%| findstr /I /C:"pack-reports" >nul && set "ACTION=pack"
  echo %RAW%| findstr /I /C:"packreports" >nul && set "ACTION=pack"
  echo %RAW%| findstr /I /C:"restart" >nul && set "ACTION=restart"
  echo %RAW%| findstr /I /C:"tray" >nul && set "ACTION=tray"
  echo %RAW%| findstr /I /C:"start" >nul && if /I not "%ACTION%"=="console" if /I not "%ACTION%"=="folder" if /I not "%ACTION%"=="setup" if /I not "%ACTION%"=="launch" if /I not "%ACTION%"=="diagnostics" if /I not "%ACTION%"=="pack" if /I not "%ACTION%"=="restart" if /I not "%ACTION%"=="tray" if /I not "%ACTION%"=="watchdog" if /I not "%ACTION%"=="watchdog-status" if /I not "%ACTION%"=="watchdog-install" if /I not "%ACTION%"=="watchdog-folder" set "ACTION=start"
)

if /I "%ACTION%"=="watchdog-status" goto do_watchdog_status
if /I "%ACTION%"=="watchdog-install" goto do_watchdog_install
if /I "%ACTION%"=="watchdog-folder" goto do_watchdog_folder
if /I "%ACTION%"=="watchdog" goto do_watchdog
if /I "%ACTION%"=="folder" goto do_folder
if /I "%ACTION%"=="setup" goto do_setup
if /I "%ACTION%"=="launch" goto do_launch
if /I "%ACTION%"=="console" goto do_console
if /I "%ACTION%"=="diagnostics" goto do_diagnostics
if /I "%ACTION%"=="pack" goto do_pack
if /I "%ACTION%"=="restart" goto do_restart
if /I "%ACTION%"=="tray" goto do_tray
goto do_start

:do_watchdog
if exist "%cd%\Start-Server-Watchdog.bat" (
  start "" "%cd%\Start-Server-Watchdog.bat"
) else if exist "%cd%\server\server_watchdog.py" (
  start "" /MIN "%cd%\.venv\Scripts\pythonw.exe" "%cd%\server\server_watchdog.py"
)
exit /b 0

:do_watchdog_status
if exist "%cd%\Open-Server-Watchdog-Status.bat" (
  start "" "%cd%\Open-Server-Watchdog-Status.bat"
) else (
  start "" explorer.exe "%LOCALAPPDATA%\FAFO\Devices\%COMPUTERNAME%\Reports"
)
exit /b 0

:do_watchdog_install
if exist "%cd%\Install-Server-Watchdog.bat" (
  start "" "%cd%\Install-Server-Watchdog.bat"
)
exit /b 0

:do_watchdog_folder
if exist "%cd%\Start-Server-Watchdog.bat" (
  start "" explorer.exe /select,"%cd%\Start-Server-Watchdog.bat"
) else (
  start "" explorer.exe "%cd%"
)
exit /b 0

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
