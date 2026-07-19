@echo off
:: Launches AI HTML Toolbox in a browser "app" window (no address bar clutter when Edge/Chrome supports --app).
setlocal
cd /d "%~dp0"

set "LAUNCHER=%~dp0Toolbox Launcher.html"
if not exist "%LAUNCHER%" (
  echo Toolbox Launcher.html not found.
  pause
  exit /b 1
)

:: Prefer Edge app mode, then Chrome, then default handler
set "URL=file:///%LAUNCHER:\=/%"
set "URL=%URL: =%%20%"

where msedge >nul 2>&1
if %errorlevel%==0 (
  start "" msedge --app="%LAUNCHER%" --new-window
  goto :done
)

if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
  start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app="%LAUNCHER%" --new-window
  goto :done
)
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
  start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app="%LAUNCHER%" --new-window
  goto :done
)
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
  start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app="%LAUNCHER%" --new-window
  goto :done
)
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
  start "" "%LocalAppData%\Google\Chrome\Application\chrome.exe" --app="%LAUNCHER%" --new-window
  goto :done
)

:: Fallback: default app for .html
start "" "%LAUNCHER%"

:done
endlocal
exit /b 0
