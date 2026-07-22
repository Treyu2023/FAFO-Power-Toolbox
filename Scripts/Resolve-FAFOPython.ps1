# Resolve-FAFOPython.ps1
# Prefer toolbox-local .venv so global site-packages stay clean.
# Prints the full path to python.exe (or pythonw.exe with -Windowed).
# Detects broken venvs (base interpreter uninstalled) and falls through.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [switch]$Windowed,
    [switch]$RequireVenv
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

function Test-PythonRuns([string]$Exe) {
    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe)) { return $false }
    try {
        $p = Start-Process -FilePath $Exe -ArgumentList @('-c', 'import sys') -Wait -PassThru -WindowStyle Hidden -ErrorAction Stop
        return ($p.ExitCode -eq 0)
    }
    catch {
        return $false
    }
}

$exeName = if ($Windowed) { 'pythonw.exe' } else { 'python.exe' }
$venvPy = Join-Path $ToolboxRoot ".venv\Scripts\$exeName"
$venvPython = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'

if (Test-Path -LiteralPath $venvPy) {
    if (Test-PythonRuns $venvPy) {
        Write-Output (Resolve-Path -LiteralPath $venvPy).Path
        return
    }
    Write-Warning "Local venv at $venvPy is broken (base Python missing). Run INSTALL-PYTHON.bat -Force"
}

if ($Windowed -and (Test-Path -LiteralPath $venvPython) -and (Test-PythonRuns $venvPython)) {
    Write-Output (Resolve-Path -LiteralPath $venvPython).Path
    return
}

if ($RequireVenv) {
    throw "Local venv not found or broken at $venvPython. Run INSTALL-PYTHON.bat first."
}

# Fallback: system Python (only if venv missing/broken)
$candidates = [System.Collections.Generic.List[string]]::new()

if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($tag in @('-3.12', '-3.11', '-3.13', '-3.10', '-3')) {
        try {
            $p = & py $tag -c "import sys; print(sys.executable)" 2>$null
            if ($p) { $candidates.Add($p.Trim()) | Out-Null }
        }
        catch { }
    }
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    try {
        $p = & python -c "import sys; print(sys.executable)" 2>$null
        if ($p -and $p -notmatch 'WindowsApps') { $candidates.Add($p.Trim()) | Out-Null }
    }
    catch { }
}

foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        'C:\Python314\python.exe',
        'C:\Python313\python.exe',
        'C:\Python312\python.exe',
        'C:\Python311\python.exe'
    )) {
    if (Test-Path -LiteralPath $p) { $candidates.Add($p) | Out-Null }
}

foreach ($c in $candidates) {
    if ($c -and (Test-PythonRuns $c)) {
        Write-Output $c
        return
    }
}

throw "Python not found. Install Python 3.10+ and run INSTALL-PYTHON.bat"
