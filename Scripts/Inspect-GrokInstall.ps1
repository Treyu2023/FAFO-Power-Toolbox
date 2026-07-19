# Inspect-GrokInstall.ps1
# Full diagnostic with organized reports (Markdown + Raw)
param(
    [string]$ToolboxRoot = "C:\Users\rkey2\OneDrive\Desktop\AI HTML TOOLBOX"
)

$ErrorActionPreference = 'SilentlyContinue'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'

$markdownFolder = Join-Path $ToolboxRoot "Reports\Markdown"
$rawFolder      = Join-Path $ToolboxRoot "Reports\Raw"
New-Item -Path $markdownFolder -ItemType Directory -Force | Out-Null
New-Item -Path $rawFolder -ItemType Directory -Force | Out-Null

$mdPath  = Join-Path $markdownFolder "GrokInstall-Report-$timestamp.md"
$rawPath = Join-Path $rawFolder      "GrokInstall-Raw-$timestamp.json"

Write-Host "=== Grok CLI Diagnostic ===" -ForegroundColor Cyan
Write-Host "Markdown report → $mdPath"
Write-Host "Raw report      → $rawPath"

$report = @"
# Grok CLI Installation Report
**Generated**: $(Get-Date)
**User**: $env:USERNAME@$env:COMPUTERNAME
**Toolbox**: $ToolboxRoot

## Command & Installation
"@

try {
    $cmd = Get-Command grok -ErrorAction Stop
    $report += "`n✅ grok found at: $($cmd.Source)`n"
    $ver = & grok --version 2>&1
    $report += "Version: $ver`n"
} catch {
    $report += "`n❌ grok command not found in PATH`n"
}

$grokHome = Join-Path $env:USERPROFILE ".grok"
if (Test-Path $grokHome) {
    $report += "`n## .grok Directory`n"
    Get-ChildItem $grokHome -Recurse | ForEach-Object {
        $report += "- $($_.FullName)`n"
    }
}

$configPath = Join-Path $grokHome "config.toml"
if (Test-Path $configPath) {
    $rawConfig = Get-Content $configPath -Raw
    $redacted = $rawConfig -replace '(?i)(api_key|key|token)\s*=\s*["''][^"'']+["'']', '$1 = "REDACTED"'
    $report += "`n## Config (redacted)`n``````toml`n$redacted`n``````"
}

$report += "`n## PATH Check`n"
$binPath = Join-Path $grokHome "bin"
if (($env:PATH -split ';') -contains $binPath) {
    $report += "✅ .grok\bin is in PATH`n"
} else {
    $report += "⚠️ .grok\bin NOT in current PATH`n"
}

$report += "`n## Sessions`n"
$sessions = Join-Path $grokHome "sessions"
if (Test-Path $sessions) {
    $count = (Get-ChildItem $sessions -Recurse | Measure-Object).Count
    $report += "$count items in sessions folder`n"
}

$report | Out-File $mdPath -Encoding UTF8

# Raw data version
$raw = [PSCustomObject]@{
    Timestamp   = $timestamp
    User        = $env:USERNAME
    GrokPath    = (Get-Command grok -ErrorAction SilentlyContinue).Source
    ConfigPath  = $configPath
    SessionsPath = $sessions
    GrokInspect = (grok inspect --json 2>&1 | ConvertFrom-Json -ErrorAction SilentlyContinue)
}
$raw | ConvertTo-Json -Depth 6 | Out-File $rawPath -Encoding UTF8

Write-Host "`n✅ Both reports created successfully." -ForegroundColor Green
Write-Host "Run this whenever you want a fresh snapshot."