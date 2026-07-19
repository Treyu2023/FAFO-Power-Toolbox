@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt 2>nul
echo [%date% %time%] start_tray_now>> startup.log
where python >> startup.log 2>&1
start "AI Toolbox Server" /MIN cmd /k "cd /d "%~dp0" && python aitoolbox_server.py"
exit /b 0