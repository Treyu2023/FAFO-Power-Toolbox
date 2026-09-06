# Start-FAFOTaskManager.ps1
# Windows Startup helper: ensure S1 is up, then open Task Manager Pro
# (autostart=1 runs the saved launch kill-profile after the page loads).

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}
$ToolboxRoot = (Resolve-Path -LiteralPath $ToolboxRoot).Path
$env:FAFO_TOOLBOX_ROOT = $ToolboxRoot

$launch = Join-Path $PSScriptRoot 'Launch-FAFOToolbox.ps1'
if (-not (Test-Path -LiteralPath $launch)) {
    throw "Missing Launch-FAFOToolbox.ps1"
}

& $launch -ToolboxRoot $ToolboxRoot -SkipSetup -Page 'System Tools/FAFO Task Manager Pro.html?autostart=1'
exit $LASTEXITCODE
