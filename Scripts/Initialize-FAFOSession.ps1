# Initialize-FAFOSession.ps1
# Loads FAFO.Secrets + FAFO.Toolbox, hydrates env, ensures paths, logs session start.

$ErrorActionPreference = 'Stop'

$ToolboxRoot = if ($env:FAFO_TOOLBOX_ROOT) {
    $env:FAFO_TOOLBOX_ROOT
}
else {
    # Scripts\ -> toolbox root
    Split-Path -Parent $PSScriptRoot
}

$env:FAFO_TOOLBOX_ROOT = $ToolboxRoot

$secretsModule = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Secrets\FAFO.Secrets.psd1'
$toolboxModule = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Toolbox\FAFO.Toolbox.psd1'

if (-not (Test-Path $secretsModule)) {
    throw "FAFO.Secrets module not found: $secretsModule"
}
if (-not (Test-Path $toolboxModule)) {
    throw "FAFO.Toolbox module not found: $toolboxModule"
}

Import-Module $secretsModule -Force
Import-Module $toolboxModule -Force

Initialize-FAFOEnvironment -Names @(
    'XAI_API_KEY',
    'ABUSE_CH_AUTH_KEY'
)

Initialize-FAFOPaths | Out-Null

Write-FAFOLog -Level Info -Message "FAFO session started (root=$ToolboxRoot)"

Write-Host "FAFO session ready. Toolbox root: $(Get-FAFOToolboxRoot)" -ForegroundColor Cyan

$health = Test-FAFOHealth
$health | Select-Object OverallOk, Failed | Format-List | Out-String | Write-Host
if (-not $health.OverallOk) {
    Write-Host "Health issues: $($health.Failed -join ', ')" -ForegroundColor Yellow
}

Write-Host "Helpers: Write-FAFOStatusReport -IncludeHealth | Invoke-FAFOGrokDiag | Get-FAFOReport | Open-FAFOPath" -ForegroundColor DarkGray
