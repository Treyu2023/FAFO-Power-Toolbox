@echo off
REM Custom protocol handler for aitoolbox:// — no browser downloads.
REM Registered by SETUP (run once).bat as:
REM   HKCU\Software\Classes\aitoolbox\shell\open\command
REM
REM Supported URLs:
REM   aitoolbox://start          Start server (minimized / tray-style)
REM   aitoolbox://console        Start server with visible console
REM   aitoolbox://folder         Open toolbox root in Explorer
REM   aitoolbox://setup          Run one-time setup
REM   aitoolbox://launch         One-click: setup if needed + server + Chrome shell
REM   aitoolbox://diagnostics    Full system diagnostics + pack report library
REM   aitoolbox://pack-reports   Rebuild catalog.js / logs-data.js only

setlocal EnableExtensions
cd /d "%~dp0.."

set "ACTION=start"
set "RAW=%~1"
if defined RAW (
  REM crude contains checks (URLs are ASCII) — more specific actions first
  echo %RAW%| findstr /I /C:"console" >nul && set "ACTION=console"
  echo %RAW%| findstr /I /C:"folder" >nul && set "ACTION=folder"
  echo %RAW%| findstr /I /C:"open" >nul && set "ACTION=folder"
  echo %RAW%| findstr /I /C:"setup" >nul && set "ACTION=setup"
  echo %RAW%| findstr /I /C:"launch" >nul && set "ACTION=launch"
  echo %RAW%| findstr /I /C:"diagnostics" >nul && set "ACTION=diagnostics"
  echo %RAW%| findstr /I /C:"pack-reports" >nul && set "ACTION=pack"
  echo %RAW%| findstr /I /C:"packreports" >nul && set "ACTION=pack"
  echo %RAW%| findstr /I /C:"start" >nul && if /I not "%ACTION%"=="console" if /I not "%ACTION%"=="folder" if /I not "%ACTION%"=="setup" if /I not "%ACTION%"=="launch" if /I not "%ACTION%"=="diagnostics" if /I not "%ACTION%"=="pack" set "ACTION=start"
)

if /I "%ACTION%"=="folder" goto do_folder
if /I "%ACTION%"=="setup" goto do_setup
if /I "%ACTION%"=="launch" goto do_launch
if /I "%ACTION%"=="console" goto do_console
if /I "%ACTION%"=="diagnostics" goto do_diagnostics
if /I "%ACTION%"=="pack" goto do_pack
goto do_start

:do_folder
start "" explorer.exe "%cd%"
exit /b 0

:do_setup
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%cd%\Scripts\Complete-FAFOSetup.ps1" -ToolboxRoot "%cd%"
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

:do_start
REM Prefer the root launcher (venv-aware, logs startup)
if exist "%cd%\START SERVER.bat" (
  start "" "%cd%\START SERVER.bat"
  exit /b 0
)
REM Fallback: start minimized from server folder
call "%~dp0..\Scripts\use-fafo-python.bat"
if errorlevel 1 exit /b 1
start "AI Toolbox Server" /MIN cmd /c "cd /d "%~dp0" && "%FAFO_PYTHON%" aitoolbox_server.py"
exit /b 0
