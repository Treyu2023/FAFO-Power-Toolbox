@echo off
cd /d "%~dp0"
start "" "%~dp0Toolbox Launcher.html"
timeout /t 1 /nobreak >nul
start "" "%~dp0System Tools\PC Reports and Log Viewer\index.html#logs"
