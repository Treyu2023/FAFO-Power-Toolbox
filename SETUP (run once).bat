@echo off
title AI Toolbox Setup
cd /d "%~dp0"

echo.
echo  AI HTML TOOLBOX — One-time setup
echo  =================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.10+ and check "Add to PATH"
    pause
    exit /b 1
)

python -m pip install -q -r server\requirements.txt
echo  [OK] Python packages installed

set "BAT=%~dp0server\protocol_start.bat"
set "BAT=%BAT:\=\\%"

reg add "HKCU\Software\Classes\aitoolbox" /ve /d "URL:AI Toolbox Server" /f >nul
reg add "HKCU\Software\Classes\aitoolbox" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\aitoolbox\DefaultIcon" /ve /d "%SystemRoot%\System32\shell32.dll,13" /f >nul
reg add "HKCU\Software\Classes\aitoolbox\shell\open\command" /ve /d "\"%~dp0server\protocol_start.bat\"" /f >nul
echo  [OK] Browser launch protocol registered (aitoolbox://start)

powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\AI Toolbox - Start Server.lnk'); $s.TargetPath='%~dp0START SERVER.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,13'; $s.Description='Start AI Toolbox Python server'; $s.Save()" 2>nul
if exist "%USERPROFILE%\Desktop\AI Toolbox - Start Server.lnk" (
    echo  [OK] Desktop shortcut created
) else (
    echo  [i] Desktop shortcut skipped — use START SERVER.bat in this folder
)

echo.
echo  Setup complete. You can now start the server from the app:
echo    - Any major tool or Launcher → "Start Server"
echo    - Or double-click START SERVER.bat
echo    - Or use Desktop shortcut "AI Toolbox - Start Server"
echo.
echo  Backend listens on http://127.0.0.87:18765
echo  (unique bind — does not conflict with FAFO on 127.0.0.1:8765)
echo.
pause