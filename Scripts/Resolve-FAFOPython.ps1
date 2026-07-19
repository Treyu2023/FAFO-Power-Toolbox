# Resolve-FAFOPython.ps1
# Prefer toolbox-local .venv so global site-packages stay clean.
# Prints the full path to python.exe (or pythonw.exe with -Windowed).

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

$exeName = if ($Windowed) { 'pythonw.exe' } else { 'python.exe' }
$venvPy = Join-Path $ToolboxRoot ".venv\Scripts\$exeName"
$venvPython = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'

if (Test-Path -LiteralPath $venvPy) {
    Write-Output (Resolve-Path -LiteralPath $venvPy).Path
    return
}
if ($Windowed -and (Test-Path -LiteralPath $venvPython)) {
    # fall back to console python if pythonw missing
    Write-Output (Resolve-Path -LiteralPath $venvPython).Path
    return
}

if ($RequireVenv) {
    throw "Local venv not found at $venvPython. Run INSTALL-PYTHON.bat first."
}

# Fallback: system Python (only if venv missing)
$candidates = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        $p = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
        if ($p) { $candidates += $p.Trim() }
    } catch {}
    try {
        $p = & py -3 -c "import sys; print(sys.executable)" 2>$null
        if ($p) { $candidates += $p.Trim() }
    } catch {}
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    try {
        $p = & python -c "import sys; print(sys.executable)" 2>$null
        if ($p) { $candidates += $p.Trim() }
    } catch {}
}

foreach ($c in $candidates) {
    if ($c -and (Test-Path -LiteralPath $c)) {
        Write-Output $c
        return
    }
}

throw "Python not found. Install Python 3.10+ (recommended 3.12) and run INSTALL-PYTHON.bat"
