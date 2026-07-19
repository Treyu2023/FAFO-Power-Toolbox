@echo off
cd /d "%~dp0"
start "AI Toolbox Server" /MIN cmd /k "cd /d "%~dp0" && python aitoolbox_server.py"
exit /b 0