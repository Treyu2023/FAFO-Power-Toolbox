# Start-FAFOShell.ps1
# Thin shell: one-click setup+server+Chrome app window.
# Optional -TopMost keeps the Chrome app window above others.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [string]$Page = 'Toolbox Launcher.html',
    [switch]$TopMost,
    [switch]$SkipSetup,
    [switch]$NoServer,
    [int]$HealthTimeoutSec = 45
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

$launch = Join-Path $PSScriptRoot 'Launch-FAFOToolbox.ps1'
if (-not (Test-Path -LiteralPath $launch)) {
    throw "Missing Launch-FAFOToolbox.ps1"
}

$args = @{
    ToolboxRoot       = $ToolboxRoot
    Page              = $Page
    HealthTimeoutSec  = $HealthTimeoutSec
}
if ($TopMost) { $args.TopMost = $true }
if ($SkipSetup) { $args.SkipSetup = $true }
if ($NoServer) { $args.NoServer = $true }

& $launch @args
exit $LASTEXITCODE
