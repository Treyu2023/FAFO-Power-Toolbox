@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt 2>nul
start /min pythonw tray_launcher.py