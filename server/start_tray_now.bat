@echo off
cd /d "%~dp0"
call "%~dp0..\Scripts\use-fafo-python.bat"
if errorlevel 1 exit /b 1
echo [%date% %time%] start_tray_now>> startup.log
echo python=%FAFO_PYTHON%>> startup.log
start "AI Toolbox Server" /MIN cmd /k "cd /d "%~dp0" && "%FAFO_PYTHON%" aitoolbox_server.py"
exit /b 0
