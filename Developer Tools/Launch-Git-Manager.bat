@echo off
title Git Repository Manager
cd /d "%~dp0\.."

echo Stopping any old AI Toolbox server on port 18765...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":18765" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Starting AI Toolbox Server on 127.0.0.87:18765...
start "AI Toolbox Server" /min cmd /c "cd /d "%~dp0..\server" && python aitoolbox_server.py"

echo Waiting for server...
timeout /t 3 /nobreak >nul

start "" "%~dp0Git Repository Manager.html"
exit
