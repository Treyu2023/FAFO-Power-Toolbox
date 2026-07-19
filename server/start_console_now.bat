@echo off
cd /d "%~dp0"
title AI Toolbox Server
python -m pip install -q -r requirements.txt 2>nul
echo [%date% %time%] Starting console server...>> startup.log
python "%~dp0aitoolbox_server.py"
pause