@echo off
cd /d "%~dp0server"
python -m pip install -q -r requirements.txt 2>nul
echo [%date% %time%] Console start>> startup.log
python aitoolbox_server.py
pause