@echo off
title AI Toolbox — Starting Server
cd /d "%~dp0"

call "%~dp0Scripts\use-fafo-python.bat"
if errorlevel 1 (
  echo  Run INSTALL-PYTHON.bat first to create .venv
  pause
  exit /b 1
)

echo.
echo  AI HTML TOOLBOX — Starting server...
echo  Python: %FAFO_PYTHON%
echo  Endpoint: http://127.0.0.87:18765  (not 127.0.0.1:8765)
echo.

REM Do not pip-install into global Python. Use INSTALL-PYTHON.bat for deps.
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo  [!] Local .venv missing — run INSTALL-PYTHON.bat once.
  echo  Falling back to system Python for this launch only.
)

echo [%date% %time%] START SERVER.bat>> "%~dp0server\startup.log"
echo python=%FAFO_PYTHON%>> "%~dp0server\startup.log"

start "AI Toolbox Server" /MIN cmd /k "cd /d "%~dp0server" && "%FAFO_PYTHON%" aitoolbox_server.py"

echo  Server window started (minimized). Check taskbar if needed.
echo  Return to Toolbox Launcher — dot should turn green in a few seconds.
echo.
timeout /t 4 /nobreak >nul
exit /b 0
