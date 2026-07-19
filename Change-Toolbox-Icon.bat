@echo off
:: Pick any .ico from your Completed ICO library and rebuild the Desktop shortcut.
cd /d "%~dp0"
set "LIB=C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO"
echo.
echo  Your icon library:
echo  %LIB%
echo.
echo  Opening folder — copy the .ico path, or drag a file onto this window...
echo.
start "" explorer "%LIB%"
echo.
set /p ICO=Full path to .ico file: 
if not exist "%ICO%" (
  echo File not found.
  pause
  exit /b 1
)
copy /Y "%ICO%" "%~dp0assets\AI-HTML-Toolbox.ico" >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Desktop-Shortcut.ps1" -IconPath "%~dp0assets\AI-HTML-Toolbox.ico" -StartMenu
echo.
echo Updated assets\AI-HTML-Toolbox.ico and Desktop shortcut.
pause
