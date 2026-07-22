@echo off
title AI Toolbox Setup
cd /d "%~dp0"

echo.
echo  AI HTML TOOLBOX — One-time setup
echo  =================================
echo.

echo  [1/3] Python virtual environment + packages
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Install-PythonEnvironment.ps1" -ToolboxRoot "%~dp0."
if errorlevel 1 (
  echo  Python environment setup failed. Try INSTALL-PYTHON.bat
  pause
  exit /b 1
)

call "%~dp0Scripts\use-fafo-python.bat"
if errorlevel 1 (
  echo  ERROR: Python still not available after install.
  pause
  exit /b 1
)
echo  [OK] Python ready: %FAFO_PYTHON%

echo.
echo  [2/3] Register browser launch protocol (aitoolbox://...)
REM Pass the full URL as %%1 so start / console / folder / setup all work without .hta downloads.
reg add "HKCU\Software\Classes\aitoolbox" /ve /d "URL:AI Toolbox Protocol" /f >nul
reg add "HKCU\Software\Classes\aitoolbox" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\aitoolbox\DefaultIcon" /ve /d "%SystemRoot%\System32\shell32.dll,13" /f >nul
reg add "HKCU\Software\Classes\aitoolbox\shell\open\command" /ve /d "\"%~dp0server\protocol_start.bat\" \"%%1\"" /f >nul
echo  [OK] Protocol registered
echo       aitoolbox://start    = start server
echo       aitoolbox://console  = start with console
echo       aitoolbox://folder   = open toolbox folder
echo       aitoolbox://setup    = run this setup again

echo.
echo  [3/3] Desktop shortcut
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\AI Toolbox - Start Server.lnk'); $s.TargetPath='%~dp0START SERVER.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,13'; $s.Description='Start AI Toolbox Python server'; $s.Save()" 2>nul
if exist "%USERPROFILE%\Desktop\AI Toolbox - Start Server.lnk" (
    echo  [OK] Desktop shortcut created
) else (
    echo  [i] Desktop shortcut skipped — use START SERVER.bat in this folder
)

echo.
echo  Setup complete.
echo    - From browser: Launcher "Start Server" uses aitoolbox://  (no .hta save prompts)
echo    - Manual: START SERVER.bat or the desktop shortcut
echo    - Backend: http://127.0.0.87:18765
echo    - Venv:    %~dp0.venv\  (local only, not committed)
echo.
echo  If Chrome asks "Open AI Toolbox Protocol?" choose Open / Always allow.
echo.
pause
