@echo off
:: Copy already-selected / library-matched icons into assets\tool-icons
:: and rebuild manifest.json so git pull shares them with everyone.
cd /d "%~dp0"
echo.
echo  Publishing shared tool icons into assets\tool-icons ...
echo  (reads icon-sources.json selections + optional library scan)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Set-FAFOToolIcon.ps1" -PublishShared -ScanLibrary
if errorlevel 1 (
  echo.
  echo  Publish failed.
  pause
  exit /b 1
)
echo.
echo  Next: commit assets\tool-icons so other machines get these icons.
echo    git add assets/tool-icons
echo    git commit -m "Share selected tool icons"
echo    git push
echo.
pause
