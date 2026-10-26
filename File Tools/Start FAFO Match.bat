@echo off
title FAFO Match
cd /d "%~dp0.."
set "PY=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=py -3"
echo FAFO Match stays up only while this window and the page are open.
start "" "http://127.0.0.1:18766/"
"%PY%" "%~dp0..\server\fafo_match_server.py"
echo Server stopped.
