# Pack THIS machine's reports into catalog.js + logs-data.js for the offline viewer.
# Source of truth: %LOCALAPPDATA%\FAFO\Devices\<COMPUTERNAME>\Reports\PC\
# Generated files are machine-local and gitignored - never commit another PC's dumps.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    # .../System Tools/PC Reports and Log Viewer -> toolbox root (up 2)
    $ToolboxRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}

$viewer = $PSScriptRoot
$modulePath = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Toolbox\FAFO.Toolbox.psd1'
if (Test-Path -LiteralPath $modulePath) {
    Import-Module $modulePath -Force
    $paths = Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot
    $deviceId = $paths.DeviceId
    $reportsDir = $paths.PcReportsDir
    $deviceRoot = $paths.DeviceRoot
}
else {
    $deviceId = ($env:COMPUTERNAME -replace '[^\w\.-]+', '-').ToUpperInvariant()
    $deviceRoot = Join-Path $env:LOCALAPPDATA "FAFO\Devices\$deviceId"
    $reportsDir = Join-Path $deviceRoot 'Reports\PC'
    New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null
}

$catalogOut = Join-Path $viewer 'catalog.js'
$logsOut = Join-Path $viewer 'logs-data.js'
$generatedAt = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')

$preferNames = @(
    'system-status-latest.html',
    'system_status_latest.md',
    'system_status_latest.txt',
    'system_snapshot_latest.json',
    'bios_system_raw.json'
)

$files = @()
if (Test-Path -LiteralPath $reportsDir) {
    $all = Get-ChildItem -LiteralPath $reportsDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -match '\.(txt|md|json|html|log)$' }
    $preferred = @()
    foreach ($n in $preferNames) {
        $hit = $all | Where-Object { $_.Name -ieq $n }
        if ($hit) { $preferred += $hit }
    }
    $rest = $all | Where-Object { $preferNames -notcontains $_.Name } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 20
    $files = @($preferred) + @($rest)
}

$logEntries = New-Object System.Collections.Generic.List[object]
$reportEntries = New-Object System.Collections.Generic.List[object]

function Get-Kind([string]$ext) {
    switch ($ext.ToLowerInvariant()) {
        '.md' { 'md' }
        '.json' { 'json' }
        '.html' { 'html' }
        default { 'log' }
    }
}

foreach ($f in $files) {
    $raw = [System.IO.File]::ReadAllText($f.FullName)
    $maxChars = 400000
    if ($raw.Length -gt $maxChars) {
        $raw = $raw.Substring(0, $maxChars) + "`n`n... [truncated for offline pack - open full file under device store] ...`n"
    }

    $id = ($f.BaseName -replace '[^\w\-]+', '-').ToLowerInvariant()
    if (-not $id) { $id = "log-$([guid]::NewGuid().ToString('N').Substring(0,8))" }

    $relFile = "device-local/Reports/PC/$($f.Name)"
    $kind = Get-Kind $f.Extension

    $title = switch -Regex ($f.Name) {
        'system-status.*\.html$' { "System Status (HTML) - $deviceId" }
        'system_status.*\.md$'   { "System Status (Markdown) - $deviceId" }
        'system_status.*\.txt$'  { "System Status (text) - $deviceId" }
        'system_snapshot'        { "System snapshot (JSON) - $deviceId" }
        'bios'                   { "BIOS / firmware snapshot - $deviceId" }
        default                  { "$($f.BaseName) - $deviceId" }
    }

    $desc = "Local to $deviceId | $($f.LastWriteTime.ToString('yyyy-MM-dd HH:mm'))"

    $logEntries.Add([ordered]@{
            id      = $id
            title   = $title
            file    = $relFile
            kind    = $kind
            desc    = $desc
            bytes   = [System.Text.Encoding]::UTF8.GetByteCount($raw)
            content = $raw
            device  = $deviceId
        }) | Out-Null

    if ($f.Extension -ieq '.html') {
        $sev = 'info'
        if ($raw -match 'banner bad|Attention needed|Kernel-Power') { $sev = 'warn' }
        if ($raw -match 'class="banner ok"') { $sev = 'ok' }
        $reportEntries.Add([ordered]@{
                id         = "rpt-$id"
                title      = $title
                summary    = "Diagnostics for $deviceId only (not other PCs)."
                category   = 'Diagnostics'
                severity   = $sev
                tags       = @($deviceId, 'This PC', 'Local')
                date       = $f.LastWriteTime.ToString('yyyy-MM-dd')
                icon       = 'heart'
                file       = $relFile
                highlights = @(
                    @{ label = 'Device'; value = $deviceId }
                    @{ label = 'Updated'; value = $f.LastWriteTime.ToString('HH:mm') }
                )
            }) | Out-Null
    }
}

if ($reportEntries.Count -eq 0) {
    $reportEntries.Add([ordered]@{
            id         = 'no-local-reports'
            title      = "No reports yet on $deviceId"
            summary    = "Run system diagnostics on this PC to populate the library. Other machines' logs stay on those machines."
            category   = 'Diagnostics'
            severity   = 'info'
            tags       = @($deviceId, 'Empty')
            date       = (Get-Date).ToString('yyyy-MM-dd')
            icon       = 'search'
            file       = ''
            highlights = @(
                @{ label = 'Device'; value = $deviceId }
                @{ label = 'Action'; value = 'Run diagnostics' }
            )
        }) | Out-Null
}

# Convert lists to plain arrays of hashtables for ConvertTo-Json reliability
$reportArr = @($reportEntries | ForEach-Object { $_ })
$logArr = @($logEntries | ForEach-Object { $_ })

$catalogObj = [PSCustomObject]@{
    generatedAt = [string]$generatedAt
    machine     = [string]$deviceId
    deviceId    = [string]$deviceId
    deviceRoot  = [string]$deviceRoot
    toolboxPath = 'System Tools\PC Reports and Log Viewer'
    scope       = 'device-local'
    note        = 'Reports and logs are for this PC only. Do not commit catalog.js / logs-data.js.'
    reports     = $reportArr
}

$catalogJson = $catalogObj | ConvertTo-Json -Depth 10 -Compress:$false
$logsJson = if ($logArr.Count -eq 0) { '[]' } else { $logArr | ConvertTo-Json -Depth 10 -Compress:$false }
if ([string]::IsNullOrWhiteSpace($logsJson)) { $logsJson = '[]' }

$catalogJs = @"
/* Auto-generated for THIS PC only ($deviceId). Do not commit.
   Refresh: Scripts\Invoke-FAFOSystemDiagnostics.ps1  OR  _pack_logs.ps1
*/
window.REPORT_CATALOG = $catalogJson;
"@

$logsJs = @"
/* Auto-generated offline Log Viewer pack for $deviceId only. Do not commit.
   Source: $reportsDir
*/
window.LOG_DATA = $logsJson;
"@

[System.IO.File]::WriteAllText($catalogOut, $catalogJs, [System.Text.UTF8Encoding]::new($false))
[System.IO.File]::WriteAllText($logsOut, $logsJs, [System.Text.UTF8Encoding]::new($false))

Write-Host "Device:  $deviceId"
Write-Host "Source:  $reportsDir"
Write-Host "Catalog: $catalogOut ($($reportEntries.Count) report cards)"
Write-Host "Logs:    $logsOut ($($logEntries.Count) log entries, $([math]::Round((Get-Item $logsOut).Length/1KB,1)) KB)"
