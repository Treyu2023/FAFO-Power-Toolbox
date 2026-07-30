@echo off
:: Stop S1 HTML Toolbox (18765) and S2 FAFO Local Media Tagger (8765)
title Stop ALL FAFO Servers
cd /d "%~dp0"

echo.
echo  Stopping S1 HTML Toolbox (127.0.0.87:18765) ...
echo  Stopping S2 FAFO Local Media Tagger (127.0.0.1:8765) ...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = @(18765, 8765); foreach ($port in $ports) { " ^
  "  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | " ^
  "    ForEach-Object { if ($_.OwningProcess -gt 0) { " ^
  "      Write-Host ('  Stopping PID ' + $_.OwningProcess + ' on port ' + $port); " ^
  "      Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } } }"

echo.
echo  Done. Tray auto-keep may restart them if still running — use tray "Stop all" or disable auto-keep.
timeout /t 2 /nobreak >nul
exit /b 0
