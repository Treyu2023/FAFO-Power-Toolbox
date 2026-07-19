@echo off
:: Pick any PNG/GIF/JPG/WEBP/ICO/SVG and set it as the shared app icon (all users).
cd /d "%~dp0"
set "LIB=C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO"
echo.
echo  Icon library (optional):
echo  %LIB%
echo.
echo  Shared icons live in: assets\tool-icons\
echo  Supported: .png .gif .jpg .webp .ico .svg .bmp
echo.
echo  Tip: to re-publish ALL already-selected tool icons, run Publish-Shared-Icons.bat
echo.
if exist "%LIB%" start "" explorer "%LIB%"
echo.
set /p ICO=Full path to image/GIF/ICO: 
if not exist "%ICO%" (
  echo File not found.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Set-FAFOToolIcon.ps1" -ToolId app -SourcePath "%ICO%" -AsAppIcon
if errorlevel 1 (
  echo Failed to set shared icon.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Desktop-Shortcut.ps1" -StartMenu
echo.
echo Updated shared app icon + Desktop shortcut.
echo Commit assets\tool-icons so other machines get the same icon.
pause
