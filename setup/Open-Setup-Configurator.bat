@echo off
title FAFO Setup Configurator
cd /d "%~dp0.."

:: Prefer same-origin URL when S1 is up
start "" "http://127.0.0.87:18765/toolbox/Setup%20Configurator.html"
exit /b 0
