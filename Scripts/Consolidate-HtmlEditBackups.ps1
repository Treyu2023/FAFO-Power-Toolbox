# Move sidecar HTML/JS/CSS .bak* copies into in-repo snapshots/<app>/ folders.
# Keep is PER APP (default 5). Pruning one tool never drops another tool's stack.
param(
    [ValidateRange(1, 50)]
    [int]$Keep = 5,

    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Initialize-FAFOSession.ps1') | Out-Null

$result = Move-FAFOHtmlEditBackups -Keep $Keep -WhatIf:$WhatIf
$result | Format-List
Write-Host ("Open: {0}" -f $result.Destination) -ForegroundColor Cyan
Write-Host ("Keep: newest {0} snapshots PER APP (not a global pool)." -f $result.KeepPerApp) -ForegroundColor DarkCyan
