#Requires -Version 5.1
<#
.SYNOPSIS
  Launch a working copy of the CITGO VAPS Pre-Reload Punch List.

.DESCRIPTION
  Copies the MASTER spreadsheet template to Working-PunchLists\ with a timestamp
  (and optional site tag), then opens the copy. The master is never modified.

.PARAMETER SiteName
  Optional site label included in the working filename (e.g. "MainSt12").

.PARAMETER NoPrompt
  Skip interactive site-name prompt when SiteName is not supplied.

.PARAMETER OpenFolder
  Open Working-PunchLists in Explorer after creating the copy (does not open Excel).
#>
[CmdletBinding()]
param(
    [string]$SiteName = '',
    [switch]$NoPrompt,
    [switch]$OpenFolder
)

$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$master = Join-Path $root 'Templates\Pre-Reload-Punch-List-MASTER.xml'
$workDir = Join-Path $root 'Working-PunchLists'

if (-not (Test-Path -LiteralPath $master)) {
    Write-Host "MASTER not found:" -ForegroundColor Red
    Write-Host "  $master" -ForegroundColor Yellow
    Write-Host "Restore Pre-Reload-Punch-List-MASTER.xml under VerifoneLibrary\Templates\" -ForegroundColor Yellow
    if (-not $env:FAFO_NONINTERACTIVE) { pause }
    exit 1
}

if (-not (Test-Path -LiteralPath $workDir)) {
    New-Item -ItemType Directory -Path $workDir -Force | Out-Null
}

if (-not $SiteName -and -not $NoPrompt) {
    try {
        $inputName = Read-Host 'Site name or ticket # for this copy (optional - press Enter to skip)'
        if ($inputName) { $SiteName = $inputName.Trim() }
    }
    catch {
        # Non-interactive host
    }
}

function Get-SafeFileToken {
    param([string]$Text, [int]$MaxLen = 40)
    if ([string]::IsNullOrWhiteSpace($Text)) { return '' }
    $t = $Text.Trim()
    $t = $t -replace '[<>:"/\\|?*\x00-\x1F]', '-'
    $t = $t -replace '\s+', '-'
    $t = $t -replace '-{2,}', '-'
    $t = $t.Trim('-')
    if ($t.Length -gt $MaxLen) { $t = $t.Substring(0, $MaxLen).TrimEnd('-') }
    return $t
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$safeSite = Get-SafeFileToken $SiteName
if ($safeSite) {
    $fileName = "Pre-Reload-PunchList_${safeSite}_${stamp}.xml"
}
else {
    $fileName = "Pre-Reload-PunchList_${stamp}.xml"
}
$dest = Join-Path $workDir $fileName

# Copy master bytes first (master file is never opened for write)
Copy-Item -LiteralPath $master -Destination $dest -Force

# Stamp working copy banner only (master stays pristine)
$xmlText = [System.IO.File]::ReadAllText($dest, [System.Text.UTF8Encoding]::new($false))
if ($safeSite) {
    $bannerNew = "WORKING COPY - site/tag: $SiteName - created $stamp. Master remains under Templates\."
}
else {
    $bannerNew = "WORKING COPY - created $stamp from master. Fill this file only. Master remains under Templates\."
}
# Match MASTER TEMPLATE banner regardless of dash character encoding
$xmlText = [regex]::Replace(
    $xmlText,
    'MASTER TEMPLATE.{0,20}open via Launch-PreReload-PunchList so a dated working copy is created\. Do not type site data into the master file\.',
    [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $bannerNew }
)
[System.IO.File]::WriteAllText($dest, $xmlText, [System.Text.UTF8Encoding]::new($false))

# Harden: confirm master still present
if (-not (Test-Path -LiteralPath $master)) {
    Write-Host 'ERROR: Master missing after copy - abort.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host 'Pre-Reload Punch List' -ForegroundColor Cyan
Write-Host '  Master (unchanged):' -ForegroundColor DarkGray
Write-Host "    $master"
Write-Host '  Working copy:' -ForegroundColor Green
Write-Host "    $dest"
Write-Host ''

if ($OpenFolder) {
    Start-Process explorer.exe -ArgumentList "`"$workDir`""
    exit 0
}

# Open with Excel if available, else default association
$excelPaths = @(
    "${env:ProgramFiles}\Microsoft Office\root\Office16\EXCEL.EXE",
    "${env:ProgramFiles(x86)}\Microsoft Office\root\Office16\EXCEL.EXE",
    "${env:ProgramFiles}\Microsoft Office\Office16\EXCEL.EXE",
    "${env:ProgramFiles(x86)}\Microsoft Office\Office16\EXCEL.EXE",
    "${env:ProgramFiles}\Microsoft Office\root\Office15\EXCEL.EXE",
    "${env:ProgramFiles(x86)}\Microsoft Office\root\Office15\EXCEL.EXE"
)
$excel = $excelPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

try {
    if ($excel) {
        Start-Process -FilePath $excel -ArgumentList "`"$dest`""
        Write-Host "Opened in Excel." -ForegroundColor Green
    }
    else {
        Start-Process -FilePath $dest
        Write-Host "Opened with default app for .xml (Excel SpreadsheetML)." -ForegroundColor Green
    }
}
catch {
    Write-Host "Could not auto-open. Open this file manually:" -ForegroundColor Yellow
    Write-Host "  $dest"
    Start-Process explorer.exe -ArgumentList "/select,`"$dest`""
}

Write-Host ''
Write-Host 'Tips: yellow cells = fillable notes; checkbox cells use dropdown empty/checked box.' -ForegroundColor DarkGray
Write-Host '      Detail sheets hold structured LAN / Loyalty / Forecourt / Security fields.' -ForegroundColor DarkGray
Write-Host ''
