@echo off
title AI Toolbox Server (Desktop)
cd /d "C:\Users\rkey2\OneDrive\Desktop\AI HTML TOOLBOX\server"
echo Starting AI Toolbox on 127.0.0.87:18765 ...
"C:\Users\rkey2\OneDrive\Desktop\AI HTML TOOLBOX\.venv\Scripts\python.exe" -u aitoolbox_server.py
echo.
echo Server stopped with code %ERRORLEVEL%
pause
