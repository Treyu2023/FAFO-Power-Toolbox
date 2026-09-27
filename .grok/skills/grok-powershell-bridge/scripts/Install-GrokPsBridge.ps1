# Install-GrokPsBridge.ps1
# Copies the skill into user + repo Grok skill dirs and can start the sidecar.

[CmdletBinding()]
param(
    [string]$ToolboxRoot,
    [switch]$Start
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    if ($env:FAFO_TOOLBOX_ROOT) { $ToolboxRoot = $env:FAFO_TOOLBOX_ROOT }
    elseif ($PSScriptRoot) {
        $here = $PSScriptRoot
        if ((Split-Path $here -Leaf) -eq 'scripts') {
            $ToolboxRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $here))
            if (-not (Test-Path (Join-Path $ToolboxRoot 'AGENTS.md'))) {
                $ToolboxRoot = Split-Path -Parent $here
            }
        } else {
            $ToolboxRoot = Split-Path -Parent $here
        }
    }
}

$skillName = 'grok-powershell-bridge'
$srcCandidates = @(
    (Join-Path $ToolboxRoot ".grok\skills\$skillName"),
    (Join-Path $PSScriptRoot '..')
) | Where-Object { Test-Path (Join-Path $_ 'SKILL.md') }

if (-not $srcCandidates) {
    throw "Cannot find $skillName SKILL.md. Run this from FAFO-Power-Toolbox."
}
$src = $srcCandidates[0]

$destinations = @(
    (Join-Path $env:USERPROFILE ".grok\skills\$skillName"),
    (Join-Path $ToolboxRoot ".grok\skills\$skillName")
)

foreach ($dest in $destinations) {
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $src '*') -Destination $dest -Recurse -Force
    Write-Host "Installed skill -> $dest" -ForegroundColor Green
}

$scriptDir = Join-Path $ToolboxRoot 'Scripts'
New-Item -ItemType Directory -Force -Path $scriptDir | Out-Null
foreach ($name in @('Start-GrokPsBridge.ps1', 'Invoke-GrokPs.ps1', 'Install-GrokPsBridge.ps1')) {
    $from = Join-Path $src "scripts\$name"
    if (Test-Path -LiteralPath $from) {
        Copy-Item -LiteralPath $from -Destination (Join-Path $scriptDir $name) -Force
        Write-Host "Installed script -> Scripts\$name" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  1. & .\Scripts\Start-GrokPsBridge.ps1"
Write-Host "  2. Restart Grok Build or run: grok inspect"
Write-Host "  3. Slash command: /grok-powershell-bridge"

if ($Start) {
    & (Join-Path $scriptDir 'Start-GrokPsBridge.ps1')
}
