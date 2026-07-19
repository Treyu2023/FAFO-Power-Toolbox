# Pack reports/*.txt|md|json into logs-data.js for offline Log Viewer
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$reports = Join-Path $root 'reports'
$out = Join-Path $root 'logs-data.js'

$files = @(
  @{ id='usb-power'; title='USB Power Fix Log'; path='USB_Power_Fix_Log.txt'; kind='log'; desc='Hub and G502 SE power-management fix output' },
  @{ id='health-1'; title='PC Health Report (raw)'; path='PC_Health_Report.txt'; kind='log'; desc='Full diagnostic dump part 1' },
  @{ id='health-2'; title='PC Health Report Part 2 (raw)'; path='PC_Health_Report_Part2.txt'; kind='log'; desc='Deep dive: disk, GPU, power, Logitech' },
  @{ id='anomaly-md'; title='Anomaly Report (Markdown source)'; path='PC_Anomaly_Report.md'; kind='md'; desc='Original markdown source' },
  @{ id='bios-json'; title='BIOS / System snapshot (JSON)'; path='bios_system_raw.json'; kind='json'; desc='Machine-readable firmware scan' }
)

$entries = New-Object System.Collections.Generic.List[object]
foreach ($f in $files) {
  $full = Join-Path $reports $f.path
  if (-not (Test-Path $full)) {
    Write-Host "skip missing $($f.path)"
    continue
  }
  $raw = [System.IO.File]::ReadAllText($full)
  $entries.Add([ordered]@{
    id = $f.id
    title = $f.title
    file = "reports/$($f.path)"
    kind = $f.kind
    desc = $f.desc
    bytes = [System.Text.Encoding]::UTF8.GetByteCount($raw)
    content = $raw
  }) | Out-Null
}

$json = $entries | ConvertTo-Json -Depth 6
$js = @"
// Auto-generated for offline Log Viewer — run _pack_logs.ps1 to refresh
window.LOG_DATA = $json;
"@
[System.IO.File]::WriteAllText($out, $js, [System.Text.UTF8Encoding]::new($false))
Write-Host "Wrote $out ($([math]::Round((Get-Item $out).Length/1KB,1)) KB) entries=$($entries.Count)"
