# Invoke-FAFOSystemDiagnostics.ps1
# One-shot system status for THIS PC only.
# Writes reports under %LOCALAPPDATA%\FAFO\Devices\<COMPUTERNAME>\
# Rebuilds PC Report Library catalog/logs packs for this machine (gitignored).
#
# Grok CLI / agents: run this when the user asks for system health, diagnostics,
# PC status, report library refresh, or "check my machine" - without requiring
# them to name individual tests.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [switch]$OpenViewer,
    [switch]$SkipEventLog,
    [int]$EventLogDays = 7,
    # Prefer Python HUD engine when .venv is available (richer report + API-compatible JSON)
    [switch]$UsePythonEngine,
    [switch]$OpenHud
)

$ErrorActionPreference = 'Continue'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

# Prefer the Python diagnostics engine (same report the HUD UI / API uses)
$venvPy = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
$pyEngine = Join-Path $ToolboxRoot 'server\pc_diagnostics.py'
$preferPython = (Test-Path -LiteralPath $venvPy) -and (Test-Path -LiteralPath $pyEngine)
if ($PSBoundParameters.ContainsKey('UsePythonEngine') -and -not $UsePythonEngine) {
    $preferPython = $false
}

if ($preferPython) {
    Write-Host "Using Python diagnostics engine (.venv)..." -ForegroundColor Cyan
    $serverDir = Join-Path $ToolboxRoot 'server'
    $skipPy = if ($SkipEventLog) { 'True' } else { 'False' }
    $pyCode = @"
import json, sys
sys.path.insert(0, r'''$serverDir''')
import pc_diagnostics as d
opts = dict(d.DEFAULT_OPTIONS)
if ${skipPy}:
    opts['event_log'] = False
report = d.run_diagnostics(options=opts, event_log_days=$EventLogDays, persist=True)
print(json.dumps({
    'ok': True,
    'overall': report.get('overall'),
    'summary': report.get('summary'),
    'meta': report.get('meta'),
}, indent=2))
"@
    & $venvPy -c $pyCode
    if ($OpenHud -or $OpenViewer) {
        $hud = Join-Path $ToolboxRoot 'System Tools\PC Diagnostics HUD.html'
        if (Test-Path -LiteralPath $hud) { Start-Process $hud }
    }
    return
}

$modulePath = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Toolbox\FAFO.Toolbox.psd1'
if (-not (Test-Path -LiteralPath $modulePath)) {
    throw "FAFO.Toolbox module not found: $modulePath"
}
Import-Module $modulePath -Force

$paths = Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot
$deviceId = $paths.DeviceId
$pcDir = $paths.PcReportsDir
$stamp = Get-Date
$stampTag = $stamp.ToString('yyyyMMdd-HHmmss')
$iso = $stamp.ToString('yyyy-MM-ddTHH:mm:ssK')
$dateOnly = $stamp.ToString('yyyy-MM-dd')

Write-Host ""
Write-Host "=== FAFO System Diagnostics ===" -ForegroundColor Cyan
Write-Host "Device : $deviceId"
Write-Host "Store  : $($paths.DeviceRoot)"
Write-Host ""

$findings = [System.Collections.Generic.List[object]]::new()
function Add-Finding {
    param(
        [ValidateSet('ok', 'warn', 'bad', 'info')][string]$Severity,
        [string]$Area,
        [string]$Message
    )
    $script:findings.Add([PSCustomObject]@{
            Severity = $Severity
            Area     = $Area
            Message  = $Message
        }) | Out-Null
}

# ---------- Collect ----------
$data = [ordered]@{
    DeviceId    = $deviceId
    CollectedAt = $iso
    Machine     = $null
    Motherboard = $null
    BIOS        = $null
    OS          = $null
    CPU         = $null
    GPUs        = @()
    Disks       = @()
    Network     = @()
    Memory      = $null
    ProblemDevices = @()
    Power       = $null
    EventSummary = $null
    Toolbox     = [ordered]@{
        Root    = $ToolboxRoot
        Version = if (Test-Path (Join-Path $ToolboxRoot 'VERSION')) {
            (Get-Content (Join-Path $ToolboxRoot 'VERSION') -Raw).Trim()
        } else { 'unknown' }
    }
}

try {
    $cs = Get-CimInstance Win32_ComputerSystem
    $bb = Get-CimInstance Win32_BaseBoard
    $bios = Get-CimInstance Win32_BIOS
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1

    $data.Machine = [ordered]@{
        ComputerName       = $cs.Name
        Manufacturer       = $cs.Manufacturer
        Model              = $cs.Model
        DomainRole         = $cs.DomainRole
        HypervisorPresent  = $cs.HypervisorPresent
        TotalRAM_GB        = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
        BootupState        = $cs.BootupState
    }
    $data.Motherboard = [ordered]@{
        Manufacturer = $bb.Manufacturer
        Product      = $bb.Product
        Version      = $bb.Version
    }
    $data.BIOS = [ordered]@{
        Manufacturer      = $bios.Manufacturer
        SMBIOSBIOSVersion = $bios.SMBIOSBIOSVersion
        ReleaseDate       = $bios.ReleaseDate
    }
    $uptime = (Get-Date) - [datetime]$os.LastBootUpTime
    $data.OS = [ordered]@{
        Caption      = $os.Caption
        Version      = $os.Version
        Build        = $os.BuildNumber
        Architecture = $os.OSArchitecture
        LastBoot     = $os.LastBootUpTime
        UptimeHours  = [math]::Round($uptime.TotalHours, 1)
        FreeRAM_GB   = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    }
    $data.CPU = [ordered]@{
        Name    = $cpu.Name.Trim()
        Cores   = $cpu.NumberOfCores
        Logical = $cpu.NumberOfLogicalProcessors
        MaxMHz  = $cpu.MaxClockSpeed
    }

    Add-Finding ok 'Identity' ("{0} | {1}" -f $cs.Name, $cs.Manufacturer)
    Add-Finding info 'OS' ("{0} build {1} | uptime {2}h" -f $os.Caption, $os.BuildNumber, [math]::Round($uptime.TotalHours, 1))
}
catch {
    Add-Finding bad 'Identity' "Failed to read system identity: $_"
}

try {
    $data.GPUs = @(Get-CimInstance Win32_VideoController | ForEach-Object {
            [ordered]@{
                Name          = $_.Name
                DriverVersion = $_.DriverVersion
                Status        = $_.Status
                AdapterRAM_GB = if ($_.AdapterRAM -and $_.AdapterRAM -gt 0) {
                    [math]::Round($_.AdapterRAM / 1GB, 1)
                } else { $null }
            }
        })
    foreach ($g in $data.GPUs) {
        if ($g.Status -and $g.Status -ne 'OK') {
            Add-Finding warn 'GPU' ("{0} status={1}" -f $g.Name, $g.Status)
        }
        else {
            Add-Finding ok 'GPU' ("{0}" -f $g.Name)
        }
    }
}
catch {
    Add-Finding warn 'GPU' "GPU query failed: $_"
}

try {
    $data.Disks = @(Get-PhysicalDisk -ErrorAction SilentlyContinue | ForEach-Object {
            [ordered]@{
                FriendlyName = $_.FriendlyName
                MediaType    = "$($_.MediaType)"
                BusType      = "$($_.BusType)"
                Size_GB      = [math]::Round($_.Size / 1GB, 0)
                Health       = "$($_.HealthStatus)"
                Operational  = "$($_.OperationalStatus)"
            }
        })
    if (-not $data.Disks.Count) {
        $data.Disks = @(Get-CimInstance Win32_DiskDrive | ForEach-Object {
                [ordered]@{
                    FriendlyName = $_.Model
                    MediaType    = $_.MediaType
                    BusType      = $_.InterfaceType
                    Size_GB      = [math]::Round($_.Size / 1GB, 0)
                    Health       = $_.Status
                    Operational  = $_.Status
                }
            })
    }
    foreach ($d in $data.Disks) {
        $h = "$($d.Health)"
        if ($h -match 'Unhealthy|Warning|Predictive') {
            Add-Finding bad 'Storage' ("{0}: {1}" -f $d.FriendlyName, $h)
        }
        elseif ($h -match 'Healthy|OK') {
            Add-Finding ok 'Storage' ("{0} ({1} GB, {2})" -f $d.FriendlyName, $d.Size_GB, $d.BusType)
        }
        else {
            Add-Finding info 'Storage' ("{0}: {1}" -f $d.FriendlyName, $h)
        }
    }
}
catch {
    Add-Finding warn 'Storage' "Disk query failed: $_"
}

try {
    $vols = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"
    foreach ($v in $vols) {
        if (-not $v.Size) { continue }
        $freePct = [math]::Round(100 * $v.FreeSpace / $v.Size, 0)
        $freeGB = [math]::Round($v.FreeSpace / 1GB, 1)
        $sizeGB = [math]::Round($v.Size / 1GB, 0)
        if ($freePct -lt 10) {
            Add-Finding bad 'Volume' ("{0}: only {1}% free ({2} GB / {3} GB)" -f $v.DeviceID, $freePct, $freeGB, $sizeGB)
        }
        elseif ($freePct -lt 15) {
            Add-Finding warn 'Volume' ("{0}: {1}% free ({2} GB / {3} GB)" -f $v.DeviceID, $freePct, $freeGB, $sizeGB)
        }
        else {
            Add-Finding ok 'Volume' ("{0}: {1}% free ({2} GB free)" -f $v.DeviceID, $freePct, $freeGB)
        }
    }
}
catch {
    Add-Finding warn 'Volume' "Volume query failed: $_"
}

try {
    $data.Network = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object Status -eq 'Up' | ForEach-Object {
            [ordered]@{
                Name      = $_.Name
                Interface = $_.InterfaceDescription
                LinkSpeed = $_.LinkSpeed
                Mac       = $_.MacAddress
            }
        })
    if ($data.Network.Count) {
        foreach ($n in $data.Network) {
            Add-Finding ok 'Network' ("{0} | {1} | {2}" -f $n.Name, $n.Interface, $n.LinkSpeed)
        }
    }
    else {
        Add-Finding warn 'Network' 'No physical adapters currently Up'
    }
}
catch {
    Add-Finding warn 'Network' "Network query failed: $_"
}

try {
    $prob = @(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.Status -ne 'OK' -and $_.Status -ne 'Unknown' } |
        Select-Object -First 25 Status, Class, FriendlyName, InstanceId)
    $data.ProblemDevices = @($prob | ForEach-Object {
            [ordered]@{
                Status = $_.Status
                Class  = $_.Class
                Name   = $_.FriendlyName
                Id     = $_.InstanceId
            }
        })
    $errorish = @($data.ProblemDevices | Where-Object { $_.Status -match 'Error|Degraded|Unknown' })
    if ($errorish.Count -gt 0) {
        Add-Finding warn 'PnP' ("{0} device(s) not OK (see report)" -f $errorish.Count)
    }
    else {
        Add-Finding ok 'PnP' 'No present devices in Error state (sampled)'
    }
}
catch {
    Add-Finding info 'PnP' "PnP query skipped: $_"
}

try {
    $mem = @(Get-CimInstance Win32_PhysicalMemory)
    $data.Memory = [ordered]@{
        Modules     = $mem.Count
        Total_GB    = [math]::Round(($mem | Measure-Object Capacity -Sum).Sum / 1GB, 0)
        Speeds_MHz  = (($mem | ForEach-Object { $_.ConfiguredClockSpeed }) | Select-Object -Unique) -join ', '
    }
    Add-Finding ok 'Memory' ("{0} modules | {1} GB | {2} MHz" -f $data.Memory.Modules, $data.Memory.Total_GB, $data.Memory.Speeds_MHz)
}
catch {
    Add-Finding info 'Memory' "Memory module query failed: $_"
}

try {
    $scheme = (powercfg /getactivescheme 2>$null | Out-String).Trim()
    $data.Power = [ordered]@{ ActiveScheme = $scheme }
    Add-Finding info 'Power' $scheme
}
catch {
    Add-Finding info 'Power' 'Could not read active power scheme'
}

# Free RAM pressure
if ($data.OS -and $data.Machine) {
    $free = [double]$data.OS.FreeRAM_GB
    $total = [double]$data.Machine.TotalRAM_GB
    if ($total -gt 0) {
        $pct = [math]::Round(100 * $free / $total, 0)
        if ($pct -lt 8) {
            Add-Finding bad 'Memory' ("Low free RAM: {0} GB free of {1} GB ({2}%)" -f $free, $total, $pct)
        }
        elseif ($pct -lt 15) {
            Add-Finding warn 'Memory' ("Tight free RAM: {0} GB free of {1} GB ({2}%)" -f $free, $total, $pct)
        }
        else {
            Add-Finding ok 'Memory' ("Free RAM: {0} GB of {1} GB ({2}%)" -f $free, $total, $pct)
        }
    }
}

# Event log summary (optional, can be slow)
if (-not $SkipEventLog) {
    Write-Host "Scanning event logs (last $EventLogDays days)..." -ForegroundColor DarkGray
    try {
        $start = (Get-Date).AddDays(-$EventLogDays)
        $sysErr = @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; Level = 1, 2, 3; StartTime = $start } -MaxEvents 500 -ErrorAction SilentlyContinue)
        $appErr = @(Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Level = 1, 2, 3; StartTime = $start } -MaxEvents 500 -ErrorAction SilentlyContinue)
        $kernel41 = @($sysErr | Where-Object { $_.Id -eq 41 -and $_.ProviderName -match 'Kernel-Power' })
        $unexpected = @($sysErr | Where-Object { $_.Id -eq 6008 })
        $topSys = $sysErr | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 8
        $topApp = $appErr | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 8

        $data.EventSummary = [ordered]@{
            Days              = $EventLogDays
            SystemEvents      = $sysErr.Count
            ApplicationEvents = $appErr.Count
            KernelPower41     = $kernel41.Count
            Unexpected6008    = $unexpected.Count
            TopSystem         = @($topSys | ForEach-Object { [ordered]@{ Provider = $_.Name; Count = $_.Count } })
            TopApplication    = @($topApp | ForEach-Object { [ordered]@{ Provider = $_.Name; Count = $_.Count } })
        }

        if ($kernel41.Count -gt 0 -or $unexpected.Count -gt 0) {
            Add-Finding bad 'Stability' ("Unexpected shutdown / Kernel-Power 41: {0}; EventLog 6008: {1}" -f $kernel41.Count, $unexpected.Count)
        }
        else {
            Add-Finding ok 'Stability' "No Kernel-Power 41 / 6008 in last $EventLogDays days (sample)"
        }

        if ($sysErr.Count -gt 200) {
            Add-Finding warn 'EventLog' ("Elevated System error/warning volume: {0} in {1}d (sampled)" -f $sysErr.Count, $EventLogDays)
        }
        else {
            Add-Finding info 'EventLog' ("System error/warning sample: {0}; Application: {1}" -f $sysErr.Count, $appErr.Count)
        }
    }
    catch {
        Add-Finding info 'EventLog' "Event log scan limited or failed: $_"
        $data.EventSummary = [ordered]@{ Error = "$_" }
    }
}
else {
    Add-Finding info 'EventLog' 'Skipped (-SkipEventLog)'
}

# ---------- Severity rollup ----------
$badN = @($findings | Where-Object Severity -eq 'bad').Count
$warnN = @($findings | Where-Object Severity -eq 'warn').Count
$okN = @($findings | Where-Object Severity -eq 'ok').Count
$overall = if ($badN -gt 0) { 'Attention needed' } elseif ($warnN -gt 0) { 'Mostly OK - review warnings' } else { 'Healthy' }
$overallSev = if ($badN -gt 0) { 'bad' } elseif ($warnN -gt 0) { 'warn' } else { 'ok' }

$data.Findings = @($findings)
$data.Overall = [ordered]@{
    Label    = $overall
    Severity = $overallSev
    Bad      = $badN
    Warn     = $warnN
    Ok       = $okN
}

# ---------- Write files ----------
$jsonPath = Join-Path $pcDir "system_snapshot_$stampTag.json"
$txtPath = Join-Path $pcDir "system_status_$stampTag.txt"
$mdPath = Join-Path $pcDir "system_status_$stampTag.md"
$htmlPath = Join-Path $pcDir "system-status-$stampTag.html"
$latestJson = Join-Path $pcDir 'system_snapshot_latest.json'
$latestTxt = Join-Path $pcDir 'system_status_latest.txt'
$latestMd = Join-Path $pcDir 'system_status_latest.md'
$latestHtml = Join-Path $pcDir 'system-status-latest.html'

$data | ConvertTo-Json -Depth 10 | Set-Content -Path $jsonPath -Encoding UTF8
Copy-Item $jsonPath $latestJson -Force

$txt = New-Object System.Text.StringBuilder
[void]$txt.AppendLine("FAFO System Status - $deviceId")
[void]$txt.AppendLine("Collected: $iso")
[void]$txt.AppendLine("Overall: $overall")
[void]$txt.AppendLine(("=" * 72))
[void]$txt.AppendLine("")
foreach ($f in $findings) {
    [void]$txt.AppendLine(("[{0,-4}] {1,-10} {2}" -f $f.Severity.ToUpper(), $f.Area, $f.Message))
}
[void]$txt.AppendLine("")
[void]$txt.AppendLine(("=" * 72))
[void]$txt.AppendLine("Raw JSON: $jsonPath")
[void]$txt.AppendLine("Device store: $($paths.DeviceRoot)")
[void]$txt.AppendLine("NOTE: This report is local to $deviceId and must not be committed to git.")
$txt.ToString() | Set-Content -Path $txtPath -Encoding UTF8
Copy-Item $txtPath $latestTxt -Force

$mdLines = @(
    "# System Status - $deviceId",
    "",
    "**Collected:** $iso  ",
    "**Overall:** $overall  ",
    "**Toolbox:** $($data.Toolbox.Version)  ",
    "",
    "## Findings",
    ""
)
foreach ($f in $findings) {
    $mdLines += "- **$($f.Severity.ToUpper())** | $($f.Area): $($f.Message)"
}
$mdLines += @(
    "",
    "## Snapshot",
    "",
    "| Field | Value |",
    "|-------|-------|",
    "| Machine | $($data.Machine.ComputerName) |",
    "| Model | $($data.Machine.Manufacturer) $($data.Machine.Model) |",
    "| Board | $($data.Motherboard.Product) |",
    "| BIOS | $($data.BIOS.SMBIOSBIOSVersion) |",
    "| OS | $($data.OS.Caption) $($data.OS.Build) |",
    "| CPU | $($data.CPU.Name) |",
    "| RAM | $($data.Machine.TotalRAM_GB) GB |",
    "",
    "Device-local path: ``$($paths.DeviceRoot)``",
    "",
    "*Do not commit these reports to the shared git repo - they belong to this PC only.*"
)
($mdLines -join "`n") | Set-Content -Path $mdPath -Encoding UTF8
Copy-Item $mdPath $latestMd -Force

# Friendly HTML for Report Library iframe
$findingRows = ($findings | ForEach-Object {
        $color = switch ($_.Severity) {
            'ok' { '#34d399' }
            'warn' { '#fbbf24' }
            'bad' { '#f43f5e' }
            default { '#60a5fa' }
        }
        "<tr><td style='color:$color;font-weight:700;text-transform:uppercase'>$($_.Severity)</td><td>$($_.Area)</td><td>$([System.Net.WebUtility]::HtmlEncode($_.Message))</td></tr>"
    }) -join "`n"

$html = @"
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<title>System Status - $deviceId</title>
<style>
  body{font-family:Segoe UI,system-ui,sans-serif;background:#0a0f18;color:#eef3fb;margin:0;padding:24px;line-height:1.5}
  h1{margin:0 0 8px;font-size:1.4rem}
  .meta{color:#8b9bb4;margin-bottom:18px}
  .banner{display:inline-block;padding:8px 14px;border-radius:999px;font-weight:800;margin-bottom:18px;
    background:rgba(139,92,246,.15);border:1px solid #3b4d6b}
  .banner.ok{color:#34d399;border-color:rgba(52,211,153,.35)}
  .banner.warn{color:#fbbf24;border-color:rgba(251,191,36,.35)}
  .banner.bad{color:#f43f5e;border-color:rgba(244,63,94,.35)}
  table{width:100%;border-collapse:collapse;background:#121a2b;border-radius:12px;overflow:hidden}
  th,td{padding:10px 12px;border-bottom:1px solid #243049;text-align:left;font-size:.92rem}
  th{color:#8b9bb4;font-size:.75rem;text-transform:uppercase;letter-spacing:.04em}
  .note{margin-top:18px;color:#8b9bb4;font-size:.85rem}
  code{color:#c4b5fd}
</style></head><body>
  <h1>System Status - $deviceId</h1>
  <div class="meta">Collected $iso | FAFO Toolbox $($data.Toolbox.Version)</div>
  <div class="banner $overallSev">$overall</div>
  <table>
    <thead><tr><th>Level</th><th>Area</th><th>Finding</th></tr></thead>
    <tbody>
      $findingRows
    </tbody>
  </table>
  <p class="note">Stored only on this PC under <code>$([System.Net.WebUtility]::HtmlEncode($paths.DeviceRoot))</code>. Not shared via git.</p>
</body></html>
"@
$html | Set-Content -Path $htmlPath -Encoding UTF8
Copy-Item $htmlPath $latestHtml -Force

# Also register in FAFO Markdown/Raw via helper
try {
    Write-FAFOReport -Name 'SystemStatus' -Content (Get-Content $mdPath -Raw) -RawObject $data -ToolboxRoot $ToolboxRoot | Out-Null
}
catch {
    Write-Host "Write-FAFOReport note: $_" -ForegroundColor DarkYellow
}

# ---------- Rebuild viewer packs for THIS device only ----------
$packScript = Join-Path $paths.ViewerDir '_pack_logs.ps1'
if (Test-Path -LiteralPath $packScript) {
    Write-Host "Rebuilding Report Library packs for $deviceId..." -ForegroundColor DarkGray
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $packScript -ToolboxRoot $ToolboxRoot
}
else {
    Write-Host "Pack script missing: $packScript" -ForegroundColor Yellow
}

# ---------- Console summary ----------
Write-Host ""
Write-Host "Overall: $overall" -ForegroundColor $(switch ($overallSev) { 'ok' { 'Green' } 'warn' { 'Yellow' } default { 'Red' } })
Write-Host ("Findings: {0} ok | {1} warn | {2} critical-ish" -f $okN, $warnN, $badN)
Write-Host ""
foreach ($f in $findings) {
    $c = switch ($f.Severity) { 'ok' { 'Green' } 'warn' { 'Yellow' } 'bad' { 'Red' } default { 'Cyan' } }
    Write-Host ("  [{0,-4}] {1,-10} {2}" -f $f.Severity.ToUpper(), $f.Area, $f.Message) -ForegroundColor $c
}
Write-Host ""
Write-Host "Reports written (this device only):" -ForegroundColor Cyan
Write-Host "  $latestHtml"
Write-Host "  $latestMd"
Write-Host "  $latestJson"
Write-Host "  Store: $($paths.DeviceRoot)"
Write-Host ""
Write-Host "Open viewer: System Tools\PC Reports and Log Viewer\index.html" -ForegroundColor DarkGray
Write-Host "Or: Open-FAFOPath -Which Viewer" -ForegroundColor DarkGray

if ($OpenViewer) {
    $idx = Join-Path $paths.ViewerDir 'index.html'
    if (Test-Path $idx) { Start-Process $idx }
}

[PSCustomObject]@{
    DeviceId     = $deviceId
    Overall      = $overall
    Severity     = $overallSev
    Findings     = @($findings)
    DeviceRoot   = $paths.DeviceRoot
    HtmlReport   = $latestHtml
    MarkdownReport = $latestMd
    JsonSnapshot = $latestJson
}
