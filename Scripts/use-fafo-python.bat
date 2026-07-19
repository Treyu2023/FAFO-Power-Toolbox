@echo off
REM Resolve FAFO toolbox Python: prefer .venv, else system python.
REM Sets FAFO_PYTHON to full path of python.exe
set "FAFO_PYTHON="
set "FAFO_ROOT=%~dp0.."
for %%I in ("%FAFO_ROOT%") do set "FAFO_ROOT=%%~fI"

if exist "%FAFO_ROOT%\.venv\Scripts\python.exe" (
  set "FAFO_PYTHON=%FAFO_ROOT%\.venv\Scripts\python.exe"
  goto :done
)

where py >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "FAFO_PYTHON=%%P"
  if defined FAFO_PYTHON goto :done
  for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "FAFO_PYTHON=%%P"
  if defined FAFO_PYTHON goto :done
)

where python >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "FAFO_PYTHON=%%P"
)

:done
if not defined FAFO_PYTHON (
  echo.
  echo  ERROR: Python not found.
  echo  Run INSTALL-PYTHON.bat once to create .venv and install requirements.
  echo.
  exit /b 1
)
exit /b 0
