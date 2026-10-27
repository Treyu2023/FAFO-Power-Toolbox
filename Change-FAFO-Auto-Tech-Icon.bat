@echo off
:: Pick a PNG, JPG, WEBP, GIF, BMP, or ICO for the FAFO Auto Technician desktop shortcut.
cd /d "%~dp0"
set "LIB=C:\Users\rkey2\OneDrive\Custom Icons and Theme\Completed ICO\Custom"
echo.
echo  FAFO Auto Technician icon
echo  Folder: %LIB%
echo  The desktop shortcut is a normal shortcut. You can also right-click it,
echo  open Properties, and choose Change Icon.
echo.
if exist "%LIB%" start "" explorer "%LIB%"
echo.
set /p ICO=Full path to the new icon (Enter keeps FAFO-Auto-Tech.ico in that folder): 
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Set-FAFOAutoTechIcon.ps1" -SourcePath "%ICO%"
if errorlevel 1 (
  echo Could not set the icon.
  pause
  exit /b 1
)
echo.
echo Desktop shortcut icon updated.
pause
