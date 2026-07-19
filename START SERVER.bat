@echo off
title AI Toolbox — Starting Server
cd /d "%~dp0server"

echo.
echo  AI HTML TOOLBOX — Starting server...
echo  Endpoint: http://127.0.0.87:18765  (not 127.0.0.1:8765)
echo.

python -m pip install -q -r requirements.txt 2>nul
echo [%date% %time%] START SERVER.bat>> startup.log

REM Minimized console — more reliable than pythonw (which fails silently)
start "AI Toolbox Server" /MIN cmd /k "cd /d "%~dp0server" && python aitoolbox_server.py"

echo  Server window started (minimized). Check taskbar if needed.
echo  Return to Toolbox Launcher — dot should turn green in a few seconds.
echo.
timeout /t 4 /nobreak >nul
exit /b 0