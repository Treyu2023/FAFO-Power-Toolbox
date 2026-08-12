@echo off
:: Sleep S1 HTML Toolbox + S2 Ultimate Tab (sticky — watchdog will NOT revive)
title Sleep ALL FAFO Servers
cd /d "%~dp0"

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\python.exe" (
  set "PY=C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\python.exe"
)

echo.
echo  S1 = HTML Toolbox     (127.0.0.87:18765)  — Toolbox apps
echo  S2 = Ultimate Tab     (127.0.0.1:8765)    — Chrome extension, NOT Toolbox
echo.
echo  Sleeping both (stop + sticky off so auto-heal will not restart them)...
echo.

if defined PY (
  "%PY%" -c "import sys; sys.path.insert(0, r'%~dp0server'); import launch_ops; r=launch_ops.sleep_companions(True, True); print('  sleeping:', r.get('sleeping')); print('  killed:', r.get('killed'))"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ports = @(18765, 8765); foreach ($port in $ports) { " ^
    "  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | " ^
    "    ForEach-Object { if ($_.OwningProcess -gt 0) { " ^
    "      Write-Host ('  Stopping PID ' + $_.OwningProcess + ' on port ' + $port); " ^
    "      Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } }"
  echo  (No .venv python — ports killed only; tray may still auto-keep unless you use tray Sleep)
)

echo.
echo  Done. Servers stay asleep until you Wake from the tray menu or Start from Launcher.
echo  Tray: right-click icon → "Sleep both" / "Wake both" or S1 / S2 submenus.
echo.
timeout /t 3 /nobreak >nul
exit /b 0
