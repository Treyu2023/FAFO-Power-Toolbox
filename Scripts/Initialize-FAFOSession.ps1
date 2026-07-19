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

$secretsModule  = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Secrets\FAFO.Secrets.psd1'
$toolboxModule  = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Toolbox\FAFO.Toolbox.psd1'
$verifoneModule = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Verifone\FAFO.Verifone.psd1'

if (-not (Test-Path $secretsModule)) {
    throw "FAFO.Secrets module not found: $secretsModule"
}
if (-not (Test-Path $toolboxModule)) {
    throw "FAFO.Toolbox module not found: $toolboxModule"
}

Import-Module $secretsModule -Force
Import-Module $toolboxModule -Force

if (Test-Path $verifoneModule) {
    Import-Module $verifoneModule -Force
}
else {
    Write-Warning "FAFO.Verifone module not found (optional): $verifoneModule"
}

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

Write-Host "Helpers: Invoke-FAFOSystemDiagnostics | Write-FAFOStatusReport -IncludeHealth | Invoke-FAFOGrokDiag | Get-FAFOReport | Open-FAFOPath -Which Device" -ForegroundColor DarkGray
Write-Host "Verifone: Set-FAFOVerifoneSitesRoot -Browse | Show-FAFOVerifoneSiteDossier | Export-FAFOVerifoneSiteDossier -Json" -ForegroundColor DarkGray
Write-Host "Sites:    local VerifoneSitesRoot (junction VerifoneLibrary\\Sites) - machine path in %LOCALAPPDATA%\\FAFO\\local-paths.json" -ForegroundColor DarkGray
Write-Host "Demo:     Add-FAFOVerifoneLibraryBackup -Path (Get-FAFOVerifoneDemoBackupPath) -Customer 'Demo Customer LLC' -Location 'Main Street 12' -Force" -ForegroundColor DarkGray
