# Install-PythonEnvironment.ps1
# Creates a local .venv under the toolbox root and installs requirements.txt.
# Does NOT install packages into the global Python environment.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,

    # Minimum supported / preferred versions
    [string]$MinVersion = '3.10',
    [string]$PreferredVersion = '3.12',

    # Recreate .venv from scratch
    [switch]$Force,

    # Skip winget attempt when Python is missing
    [switch]$NoWingetInstall
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}
if (-not (Test-Path -LiteralPath $ToolboxRoot)) {
    throw "Toolbox root not found: $ToolboxRoot"
}

$env:FAFO_TOOLBOX_ROOT = $ToolboxRoot
$reqRoot = Join-Path $ToolboxRoot 'requirements.txt'
$reqServer = Join-Path $ToolboxRoot 'server\requirements.txt'
$venvDir = Join-Path $ToolboxRoot '.venv'
$venvPy = Join-Path $venvDir 'Scripts\python.exe'
$venvPip = Join-Path $venvDir 'Scripts\pip.exe'

function Write-Step([string]$Message, [string]$Color = 'Cyan') {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor $Color
}

function Test-PythonVersionOk([string]$Exe, [version]$Min) {
    try {
        $raw = & $Exe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if (-not $raw) { return $false }
        $v = [version]($raw.Trim())
        return ($v -ge $Min)
    }
    catch {
        return $false
    }
}

function Find-SystemPython {
    $min = [version]$MinVersion
    $found = @()

    # py launcher first (Windows)
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($tag in @("-3.12", "-3.11", "-3.10", "-3")) {
            try {
                $exe = & py $tag -c "import sys; print(sys.executable)" 2>$null
                if ($exe -and (Test-Path $exe.Trim()) -and (Test-PythonVersionOk $exe.Trim() $min)) {
                    $found += [PSCustomObject]@{ Exe = $exe.Trim(); Via = "py $tag" }
                }
            }
            catch { }
        }
    }

    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -and (Test-PythonVersionOk $cmd.Source $min)) {
            # Skip WindowsApps stub that opens Store
            if ($cmd.Source -match 'WindowsApps') { continue }
            $found += [PSCustomObject]@{ Exe = $cmd.Source; Via = $name }
        }
    }

    # Common install paths
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )
    foreach ($p in $paths) {
        if ((Test-Path $p) -and (Test-PythonVersionOk $p $min)) {
            $found += [PSCustomObject]@{ Exe = $p; Via = 'path' }
        }
    }

    # Prefer 3.12
    $prefer = $found | Where-Object { $_.Exe -match 'Python312|3\.12' } | Select-Object -First 1
    if ($prefer) { return $prefer }
    return $found | Select-Object -First 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AI HTML Toolbox - Python environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Root: $ToolboxRoot"
Write-Host "Venv: $venvDir"
Write-Host "Python: $MinVersion+ required, $PreferredVersion recommended"
Write-Host "Packages install ONLY into .venv (not global)."

# --- Locate base interpreter ---
Write-Step "Looking for system Python $MinVersion+"
$base = Find-SystemPython

if (-not $base) {
    Write-Host "Python $MinVersion+ not found on PATH." -ForegroundColor Yellow

    if (-not $NoWingetInstall -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Step "Installing Python $PreferredVersion via winget (user scope)"
        $id = if ($PreferredVersion -eq '3.12') { 'Python.Python.3.12' } else { 'Python.Python.3.12' }
        & winget install --id $id -e --accept-source-agreements --accept-package-agreements --disable-interactivity
        # Refresh PATH for this process
        $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                    [System.Environment]::GetEnvironmentVariable('Path', 'User')
        $base = Find-SystemPython
    }

    if (-not $base) {
        Write-Host ""
        Write-Host "Could not find or install Python automatically." -ForegroundColor Red
        Write-Host "Install manually, then re-run this script:"
        Write-Host '  https://www.python.org/downloads/  (3.12.x recommended)'
        Write-Host '  Check: Add python.exe to PATH'
        Write-Host '  Check: py launcher'
        Write-Host ''
        Write-Host 'Or: winget install Python.Python.3.12'
        exit 1
    }
}

Write-Host "Using base interpreter: $($base.Exe) ($($base.Via))" -ForegroundColor Green
& $base.Exe --version

# --- requirements file ---
$req = if (Test-Path $reqRoot) { $reqRoot } elseif (Test-Path $reqServer) { $reqServer } else {
    throw 'No requirements.txt found at repo root or server\'
}
Write-Host "Requirements: $req"

# --- Create venv ---
if ($Force -and (Test-Path $venvDir)) {
    Write-Step "Removing existing .venv (-Force)"
    Remove-Item -LiteralPath $venvDir -Recurse -Force
}

if (-not (Test-Path $venvPy)) {
    Write-Step "Creating virtual environment at .venv"
    & $base.Exe -m venv $venvDir
    if (-not (Test-Path $venvPy)) {
        throw "venv creation failed - missing $venvPy"
    }
}
else {
    Write-Host "Existing venv found: $venvPy" -ForegroundColor DarkGray
}

# --- Upgrade pip tooling inside venv only ---
Write-Step "Upgrading pip / setuptools / wheel (inside .venv)"
& $venvPy -m pip install --upgrade pip setuptools wheel

# --- Install project deps into venv ---
Write-Step "Installing requirements into .venv"
& $venvPy -m pip install -r $req

# --- Sanity checks ---
Write-Step "Verifying imports"
& $venvPy -c @"
import sys
print('python', sys.version)
print('prefix', sys.prefix)
mods = ['fastapi', 'uvicorn', 'mutagen', 'PIL', 'pystray', 'psutil']
if sys.platform == 'win32':
    mods.append('win32api')
for m in mods:
    __import__(m if m != 'PIL' else 'PIL')
    print('  OK', m)
print('venv-ok')
"@

# Marker file for bats
$marker = Join-Path $venvDir 'fafo-toolbox-venv.txt'
@"
FAFO / AI HTML Toolbox local virtualenv
Created: $(Get-Date -Format o)
Base: $($base.Exe)
Do not commit this folder. Recreate with INSTALL-PYTHON.bat
"@ | Set-Content -Path $marker -Encoding UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Environment ready" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "Python (venv): $venvPy"
Write-Host "Activate (optional interactive shell):"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Start the toolbox server:"
Write-Host "  .\START SERVER.bat"
Write-Host "  (uses .venv automatically)"
Write-Host ""
Write-Host "Global Python packages were NOT modified."
Write-Host ""
