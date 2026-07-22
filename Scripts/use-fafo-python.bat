@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Resolve FAFO toolbox Python: prefer a WORKING local .venv, else system python.
REM Sets FAFO_PYTHON in the CALLER environment (via endlocal trick).
REM
REM Broken venvs (base interpreter uninstalled) print:
REM   No Python at '"C:\...\Python312\python.exe'
REM and must not be used.

set "FAFO_PYTHON="
set "FAFO_ROOT=%~dp0.."
for %%I in ("%FAFO_ROOT%") do set "FAFO_ROOT=%%~fI"

REM --- 1) Local .venv if it actually runs ---
if exist "%FAFO_ROOT%\.venv\Scripts\python.exe" (
  "%FAFO_ROOT%\.venv\Scripts\python.exe" -c "import sys" >nul 2>&1
  if not errorlevel 1 (
    set "FAFO_PYTHON=%FAFO_ROOT%\.venv\Scripts\python.exe"
    goto :export
  )
  echo.
  echo  [!] Local .venv is broken ^(base Python was moved/uninstalled^).
  echo      Run INSTALL-PYTHON.bat to recreate .venv
  echo.
)

REM --- 2) py launcher ---
where py >nul 2>&1
if not errorlevel 1 (
  for %%V in (3.12 3.11 3.13 3.10 3) do (
    if not defined FAFO_PYTHON (
      for /f "delims=" %%P in ('py -%%V -c "import sys; print(sys.executable)" 2^>nul') do (
        if exist "%%P" (
          "%%P" -c "import sys" >nul 2>&1
          if not errorlevel 1 set "FAFO_PYTHON=%%P"
        )
      )
    )
  )
)

if defined FAFO_PYTHON goto :export

REM --- 3) python on PATH ---
where python >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do (
    echo %%P| findstr /I "WindowsApps" >nul
    if errorlevel 1 (
      if exist "%%P" (
        "%%P" -c "import sys" >nul 2>&1
        if not errorlevel 1 set "FAFO_PYTHON=%%P"
      )
    )
  )
)

if defined FAFO_PYTHON goto :export

REM --- 4) Common install locations ---
for %%P in (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
  "%ProgramFiles%\Python312\python.exe"
  "%ProgramFiles%\Python311\python.exe"
  "C:\Python314\python.exe"
  "C:\Python313\python.exe"
  "C:\Python312\python.exe"
  "C:\Python311\python.exe"
) do (
  if not defined FAFO_PYTHON (
    if exist %%P (
      %%P -c "import sys" >nul 2>&1
      if not errorlevel 1 set "FAFO_PYTHON=%%~fP"
    )
  )
)

:export
if not defined FAFO_PYTHON (
  echo.
  echo  ERROR: No working Python found.
  echo  Run INSTALL-PYTHON.bat once to create .venv and install requirements.
  echo  ^(Your previous .venv may point at a removed Python 3.12 install.^)
  echo.
  endlocal
  exit /b 1
)

REM Warn if not using local venv
echo !FAFO_PYTHON!| findstr /I /C:"\.venv\Scripts\python.exe" >nul
if errorlevel 1 (
  echo  [!] Using system Python: !FAFO_PYTHON!
  echo      Prefer a local .venv — run INSTALL-PYTHON.bat
)

REM Export to caller (setlocal would otherwise discard)
endlocal & set "FAFO_PYTHON=%FAFO_PYTHON%" & set "FAFO_ROOT=%FAFO_ROOT%"
exit /b 0
