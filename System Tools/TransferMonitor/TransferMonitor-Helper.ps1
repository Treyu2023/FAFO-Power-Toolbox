#requires -Version 5.1
<#
.SYNOPSIS
  Transfer Monitor live helper: read-only loopback JSON endpoint for the toolbox page.

.DESCRIPTION
  Read-only monitoring helper. No process control, no writes except its own token file
  (.env.transfer-token.js beside this script; gitignored by the root .env.* rule).
  Listens on 127.0.0.1 only through a raw TcpListener (no HTTP.sys prefix, no URL ACL).
  Routes: GET /health and GET /transfers. Serves no files and reads no request body.
  Started by S1 (/api/tools/launch id "transfer-helper"); exits by itself after
  -IdleMinutes without a /transfers request. One instance per port.
  /transfers serves real partial downloads only: files under *_files folders and *.js/*.css.download
  (saved-page assets) and BITS jobs not Transferring/Queued/Connecting/TransientError are left out;
  partials untouched for more than 24 h are only counted (counts.stale). The collector below is unchanged.

  Copied verbatim from TransferMonitor.ps1 (same folder):
    L26-36    $script:WatchStore + Read-WatchFolders (read-only; the L37-43 writer is not copied)
    L151-340  Format-Bytes, Format-Rate, Get-StableKey, $script:State, $partialPatterns,
              $procNames, New-Transfer, Add-History, Get-PartialTransfers, Get-BitsTransfers,
              Get-ProcessTransfers, Update-NetRates, Merge-Snapshot
  Not copied: the desktop UI (L1-25, L44-150, L342-1010) and its demo row (L875-883).
#>
param(
  [int]$Port = 18769,
  [string]$BindAddress = '127.0.0.1',
  [int]$IdleMinutes = 10,
  [int]$PollMs = 1500,
  [int]$HistoryMax = 200,
  [string[]]$WatchFolders = @(
    "$env:USERPROFILE\Downloads",
    "$env:USERPROFILE\Desktop",
    "$env:LOCALAPPDATA\Temp\WinGet"
  )
)

# Validation first: nothing is created (no mutex, no socket, no file) before these pass.
if ($BindAddress -ne '127.0.0.1') {
  [Console]::Error.WriteLine("refusing non-loopback bind: $BindAddress")
  exit 2
}
if ($Port -lt 1024 -or $Port -gt 65535 -or (@(8765, 18765, 18767, 17321) -contains $Port)) {
  [Console]::Error.WriteLine("refusing port: $Port")
  exit 2
}

# ---- copied verbatim from TransferMonitor.ps1 L26-36 ----
$script:WatchStore = Join-Path $env:LOCALAPPDATA 'FAFO\TransferMonitor\watch-folders.json'
function Read-WatchFolders {
  if (Test-Path -LiteralPath $script:WatchStore) {
    try {
      $j = Get-Content -LiteralPath $script:WatchStore -Raw -Encoding UTF8 | ConvertFrom-Json
      $list = @($j.folders | ForEach-Object { [string]$_ } | Where-Object { $_ })
      if ($list.Count -gt 0) { return $list }
    } catch {}
  }
  return @($WatchFolders)
}
# ---- end of L26-36 ----

$script:WatchLive = New-Object System.Collections.Generic.List[string]
$script:WatchExplicit = $PSBoundParameters.ContainsKey('WatchFolders')
$script:WatchAt = [datetime]::MinValue
function Update-WatchLive {
  # At most every 30 s. Same de-dup as TransferMonitor.ps1 L44-47. Never writes watch-folders.json.
  $now = Get-Date
  if (($now - $script:WatchAt).TotalSeconds -lt 30) { return }
  $script:WatchAt = $now
  $src = if ($script:WatchExplicit) { @($WatchFolders) } else { @(Read-WatchFolders) }
  $script:WatchLive.Clear()
  foreach ($f in $src) {
    if ($f -and -not $script:WatchLive.Contains($f)) { [void]$script:WatchLive.Add($f) }
  }
}

# ---- copied verbatim from TransferMonitor.ps1 L151-340 ----
function Format-Bytes([long]$n) {
  if ($n -lt 0) { return '?' }
  $u = @('B','KB','MB','GB','TB')
  $v = [double]$n
  $i = 0
  while ($v -ge 1024 -and $i -lt $u.Count - 1) { $v /= 1024; $i++ }
  if ($i -eq 0) { return ("{0} {1}" -f [int]$v, $u[$i]) }
  return ("{0:N2} {1}" -f $v, $u[$i])
}

function Format-Rate([double]$bps) {
  if ($bps -le 0) { return '-' }
  return ("{0}/s" -f (Format-Bytes ([long]$bps)))
}

function Get-StableKey($kind, $id) { return "$kind::$id" }

$script:State = @{
  Active      = @{}
  History     = New-Object System.Collections.Generic.List[object]
  SeenDone    = @{}
  AnimPhase   = 0.0
  NetInRate   = 0.0
  NetOutRate  = 0.0
  LastTick    = [Environment]::TickCount
  NetTick     = 0
  HistDirty   = $true
  UserBusy    = $false
  AnimTick    = 0
}

$partialPatterns = @(
  '*.partial', '*.crdownload', '*.opdownload', '*.download', '*.aria2',
  'Unconfirmed *.crdownload', 'Unconfirmed*.crdownload'
)

$procNames = @(
  'curl','wget','aria2c','rclone','scp','sftp','pscp','psftp',
  'megacmd','mega-get','qbittorrent','transmission-qt','deluge',
  'IDMan','FreeDownloadManager','motrix','yt-dlp','ffmpeg'
)

function New-Transfer {
  param(
    [string]$Key, [string]$Name,
    [ValidateSet('In','Out','Unknown')]$Direction,
    [string]$Protocol, [string]$Source,
    [long]$Bytes = 0, [long]$Total = 0,
    [string]$Path = '', [string]$Detail = ''
  )
  [pscustomobject]@{
    Key=$Key; Name=$Name; Direction=$Direction; Protocol=$Protocol; Source=$Source
    Bytes=$Bytes; Total=$Total; Path=$Path; Detail=$Detail
    Rate=0.0; PrevBytes=$Bytes; FirstSeen=(Get-Date); LastSeen=(Get-Date)
    DisplayPct=0.0; Status='Active'
  }
}

function Add-History($t, [string]$status) {
  if ($script:State.SeenDone.ContainsKey($t.Key)) { return }
  $script:State.SeenDone[$t.Key] = $true
  $row = [pscustomobject]@{
    Time=(Get-Date); Status=$status; Name=$t.Name; Direction=$t.Direction
    Protocol=$t.Protocol; Bytes=$t.Bytes; Total=$t.Total; Path=$t.Path
    Source=$t.Source; Detail=$t.Detail
    DurationS=[math]::Max(0, ((Get-Date) - $t.FirstSeen).TotalSeconds)
    Key=$t.Key
  }
  $script:State.History.Insert(0, $row)
  while ($script:State.History.Count -gt $HistoryMax) {
    $script:State.History.RemoveAt($script:State.History.Count - 1)
  }
  $script:State.HistDirty = $true
}

function Get-PartialTransfers {
  $found = @{}
  foreach ($folder in @($script:WatchLive)) {
    if (-not (Test-Path -LiteralPath $folder)) { continue }
    foreach ($pat in $partialPatterns) {
      Get-ChildItem -LiteralPath $folder -Filter $pat -File -Force -Recurse -Depth 3 -ErrorAction SilentlyContinue | ForEach-Object {
        $key = Get-StableKey 'file' $_.FullName
        $name = $_.Name -replace '\.(partial|crdownload|opdownload|download|aria2)$',''
        $proto = switch -Regex ($_.Extension) {
          '\.crdownload' { 'Browser' }
          '\.opdownload' { 'Browser' }
          '\.partial'    { 'Partial' }
          '\.aria2'      { 'aria2' }
          default        { 'Download' }
        }
        $found[$key] = New-Transfer -Key $key -Name $name -Direction 'In' -Protocol $proto `
          -Source $folder -Bytes ([long]$_.Length) -Path $_.FullName `
          -Detail ("Mod {0:HH:mm:ss}" -f $_.LastWriteTime)
      }
    }
  }
  return $found
}

function Get-BitsTransfers {
  $found = @{}
  try {
    foreach ($j in @(Get-BitsTransfer -ErrorAction SilentlyContinue)) {
      if (-not $j) { continue }
      $bytes = 0L; $total = 0L
      try { $bytes = [long]$j.BytesTransferred } catch {}
      try { $total = [long]$j.BytesTotal } catch {}
      $name = if ($j.DisplayName) { $j.DisplayName } else { $j.JobId.ToString() }
      $dir = 'In'
      try { if ($j.TransferType -match 'Upload') { $dir = 'Out' } } catch {}
      $key = Get-StableKey 'bits' $j.JobId.ToString()
      $files = ''
      try { $files = ($j.FileList | ForEach-Object { $_.LocalName } | Select-Object -First 1) } catch {}
      $found[$key] = New-Transfer -Key $key -Name $name -Direction $dir -Protocol 'BITS' `
        -Source 'BITS' -Bytes $bytes -Total $total -Path $files -Detail ("State: {0}" -f $j.JobState)
    }
  } catch {}
  return $found
}

function Get-ProcessTransfers {
  $found = @{}
  foreach ($pn in $procNames) {
    Get-Process -Name $pn -ErrorAction SilentlyContinue | ForEach-Object {
      $key = Get-StableKey 'proc' ("{0}:{1}" -f $_.ProcessName, $_.Id)
      $dir = if ($_.ProcessName -match 'rclone|scp|pscp|sftp') { 'Unknown' } else { 'In' }
      $found[$key] = New-Transfer -Key $key -Name ("{0} #{1}" -f $_.ProcessName, $_.Id) `
        -Direction $dir -Protocol 'Process' -Source $_.ProcessName `
        -Detail ("WS {0}" -f (Format-Bytes $_.WorkingSet64))
    }
  }
  return $found
}

function Update-NetRates {
  try {
    $inSamples = (Get-Counter '\Network Interface(*)\Bytes Received/sec' -ErrorAction Stop).CounterSamples |
      Where-Object { $_.InstanceName -notmatch 'isatap|loopback|Teredo' }
    $outSamples = (Get-Counter '\Network Interface(*)\Bytes Sent/sec' -ErrorAction Stop).CounterSamples |
      Where-Object { $_.InstanceName -notmatch 'isatap|loopback|Teredo' }
    $in = @($inSamples | Measure-Object -Property CookedValue -Sum).Sum
    $out = @($outSamples | Measure-Object -Property CookedValue -Sum).Sum
    if ($null -ne $in) { $script:State.NetInRate = [double]$in }
    if ($null -ne $out) { $script:State.NetOutRate = [double]$out }
  } catch {}
}

function Merge-Snapshot {
  $now = Get-Date
  $tick = [Environment]::TickCount
  $dt = [math]::Max(0.05, ([uint32]($tick - $script:State.LastTick)) / 1000.0)
  $script:State.LastTick = $tick

  $snap = @{}
  foreach ($map in @((Get-PartialTransfers), (Get-BitsTransfers), (Get-ProcessTransfers))) {
    if ($map -is [hashtable]) { foreach ($k in $map.Keys) { $snap[$k] = $map[$k] } }
  }

  foreach ($k in @($snap.Keys)) {
    $n = $snap[$k]
    if ($script:State.Active.ContainsKey($k)) {
      $a = $script:State.Active[$k]
      $delta = [double]($n.Bytes - $a.PrevBytes)
      if ($delta -ge 0) { $a.Rate = $delta / $dt }
      $a.PrevBytes = $n.Bytes; $a.Bytes = $n.Bytes
      if ($n.Total -gt 0) { $a.Total = $n.Total }
      $a.LastSeen = $now; $a.Detail = $n.Detail; $a.Path = $n.Path
      $target = if ($a.Total -gt 0) { [math]::Min(100.0, 100.0 * $a.Bytes / $a.Total) } else { -1.0 }
      $a.DisplayPct = if ($target -ge 0) { $a.DisplayPct + ($target - $a.DisplayPct) * 0.3 } else { -1.0 }
    } else {
      $n.PrevBytes = $n.Bytes; $n.Rate = 0
      $script:State.Active[$k] = $n
    }
  }

  foreach ($k in @($script:State.Active.Keys)) {
    if (-not $snap.ContainsKey($k)) {
      $a = $script:State.Active[$k]
      if (((Get-Date) - $a.LastSeen).TotalSeconds -gt 1.5) {
        Add-History $a $(if ($a.Bytes -gt 0) { 'Completed' } else { 'Ended' })
        $script:State.Active.Remove($k)
      }
    }
  }

  $script:State.NetTick++
  # Get-Counter is expensive — only every ~8s
  if (($script:State.NetTick % 7) -eq 0) { Update-NetRates }
  $script:State.AnimPhase = ($script:State.AnimPhase + $dt * 0.9) % 1.0
}
# ---- end of L151-340 ----

$script:LastCollect = [datetime]::MinValue
$script:StaleAfter = [TimeSpan]::FromHours(24)
$script:View = @{}    # key -> 'show' | 'stale' | 'skip' at the last collect (served view only; State is untouched)
$script:Shown = @{}   # keys served as active at least once; only their history rows are served
function Invoke-Collect {
  $ErrorActionPreference = 'SilentlyContinue'
  if (((Get-Date) - $script:LastCollect).TotalMilliseconds -lt $PollMs) { return }
  $script:LastCollect = Get-Date
  Update-WatchLive
  try { Merge-Snapshot } catch {}
  try { Update-TmView } catch {}
}

function Get-TmClass($t) {
  # Served-view rules only: never adds, removes or moves State items, so no history row comes from a rule.
  $k = [string]$t.Key
  if ($k.StartsWith('bits::')) {
    if ([string]$t.Detail -match '^State: (Transferring|Queued|Connecting|TransientError)$') { return 'show' }
    return 'skip'
  }
  if (-not $k.StartsWith('file::')) { return 'show' }                     # processes
  $p = [string]$t.Path; $src = [string]$t.Source
  if ($p -match '\.(js|css)\.download$') { return 'skip' }              # saved-page asset anywhere
  $rel = $p
  if ($src -and $p.StartsWith($src, [StringComparison]::OrdinalIgnoreCase)) { $rel = $p.Substring($src.Length) }
  if ($rel -match '(^|\\)[^\\]*_files\\') { return 'skip' }        # under a *_files folder below the watched root
  try { $m = [System.IO.File]::GetLastWriteTimeUtc($p) } catch { return 'show' }
  if ($m.Year -lt 1700) { return 'show' }                                 # gone: the collector drops it next pass
  if (([datetime]::UtcNow - $m) -gt $script:StaleAfter) { return 'stale' }
  return 'show'
}

function Update-TmView {
  $v = @{}
  foreach ($t in @($script:State.Active.Values)) {
    $k = [string]$t.Key; $c = Get-TmClass $t; $v[$k] = $c
    if ($c -eq 'show') { $script:Shown[$k] = $true }
  }
  $script:View = $v
}

function ConvertTo-IsoUtc($d) {
  if ($d -is [datetime]) { return $d.ToUniversalTime().ToString('o') }
  return $null
}

function ConvertTo-TmJson {
  $active = [object[]]@($script:State.Active.Values | Where-Object { $c = $script:View[[string]$_.Key]; (-not $c) -or $c -eq 'show' } |
    Sort-Object -Property @{ Expression = { [double]$_.Rate }; Descending = $true }, @{ Expression = { [string]$_.Name }; Descending = $false } |
    ForEach-Object {
      $pct = if ([long]$_.Total -gt 0) { [math]::Round(100.0 * [double]$_.Bytes / [double]$_.Total, 1) } else { -1 }
      [ordered]@{
        key = [string]$_.Key; name = [string]$_.Name; direction = [string]$_.Direction
        protocol = [string]$_.Protocol; source = [string]$_.Source
        bytes = [long]$_.Bytes; total = [long]$_.Total; pct = $pct; rateBps = [double]$_.Rate
        path = [string]$_.Path; detail = [string]$_.Detail
        firstSeen = (ConvertTo-IsoUtc $_.FirstSeen); lastSeen = (ConvertTo-IsoUtc $_.LastSeen)
        status = [string]$_.Status
      }
    })
  $history = [object[]]@($script:State.History | Where-Object { $script:Shown.ContainsKey([string]$_.Key) } |
    Select-Object -First 50 | ForEach-Object {
      [ordered]@{
        time = (ConvertTo-IsoUtc $_.Time); status = [string]$_.Status; name = [string]$_.Name
        direction = [string]$_.Direction; protocol = [string]$_.Protocol
        bytes = [long]$_.Bytes; total = [long]$_.Total; path = [string]$_.Path
        source = [string]$_.Source; detail = [string]$_.Detail
        durationS = [math]::Round([double]$_.DurationS, 1); key = [string]$_.Key
      }
    })
  $o = [ordered]@{
    ok = $true; service = 'fafo-transfer-helper'; schema = 1; readOnly = $true
    at = (Get-Date).ToUniversalTime().ToString('o'); pollMs = $PollMs; staleHours = [int]$script:StaleAfter.TotalHours
    watchFolders = [object[]]@($script:WatchLive)
    net = [ordered]@{ inBps = [double]$script:State.NetInRate; outBps = [double]$script:State.NetOutRate }
    active = $active; history = $history
    counts = [ordered]@{ active = $active.Count; history = $history.Count; stale = @($script:View.Values | Where-Object { $_ -eq 'stale' }).Count }
  }
  return ($o | ConvertTo-Json -Depth 5 -Compress)
}

# ---- per-launch token (never logged, never returned in a body) ----
function New-TmToken {
  $bytes = New-Object byte[] 32
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
  return ([Convert]::ToBase64String($bytes)).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}
$script:Token = New-TmToken
$script:TokenBytes = [System.Text.Encoding]::ASCII.GetBytes($script:Token)
$script:TokenLine = 'window.FAFO_TM_TOKEN="' + $script:Token + '";'
$script:TokenFile = Join-Path $PSScriptRoot '.env.transfer-token.js'
$script:TokenWritten = $false

function Write-TmTokenFile {
  # Only in the real app folder (the page must sit beside this script); otherwise file:// stays locked out.
  if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'Transfer Monitor.html'))) { return }
  $tmp = "$($script:TokenFile).$PID.tmp"
  try {
    [System.IO.File]::WriteAllText($tmp, $script:TokenLine, (New-Object System.Text.UTF8Encoding($false)))
    if (Test-Path -LiteralPath $script:TokenFile) {
      [System.IO.File]::Replace($tmp, $script:TokenFile, [NullString]::Value)
    } else {
      [System.IO.File]::Move($tmp, $script:TokenFile)
    }
    $script:TokenWritten = $true
  } catch {
    try { if (Test-Path -LiteralPath $tmp) { [System.IO.File]::Delete($tmp) } } catch {}
  }
}

function Remove-TmTokenFile {
  if (-not $script:TokenWritten) { return }
  try {
    if ((Test-Path -LiteralPath $script:TokenFile) -and ([System.IO.File]::ReadAllText($script:TokenFile) -eq $script:TokenLine)) {
      [System.IO.File]::Delete($script:TokenFile)
    }
  } catch {}
}

function Test-TmToken([string]$got) {
  # Fixed-time: XOR accumulated over the full token length whatever the input.
  if ([string]::IsNullOrEmpty($got)) { return $false }
  $g = [System.Text.Encoding]::ASCII.GetBytes($got)
  $t = $script:TokenBytes
  $diff = $g.Length -bxor $t.Length
  for ($i = 0; $i -lt $t.Length; $i++) {
    $b = 0
    if ($i -lt $g.Length) { $b = $g[$i] }
    $diff = $diff -bor ($b -bxor $t[$i])
  }
  return ($diff -eq 0)
}

# ---- HTTP over a loopback TcpListener ----
$ToolboxOrigins = @('http://127.0.0.87:18765', 'http://127.0.0.1:18765')
$script:Reasons = @{ 200 = 'OK'; 204 = 'No Content'; 400 = 'Bad Request'; 403 = 'Forbidden'; 404 = 'Not Found'; 405 = 'Method Not Allowed'; 431 = 'Request Header Fields Too Large' }

function Send-TmResponse($stream, [int]$code, [string]$body, [string]$acao, [System.Collections.IDictionary]$extra, [bool]$headOnly) {
  $bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$body)
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.Append("HTTP/1.1 $code $($script:Reasons[$code])`r`n")
  if ($bytes.Length -gt 0) { [void]$sb.Append("Content-Type: application/json; charset=utf-8`r`n") }
  [void]$sb.Append("Content-Length: $($bytes.Length)`r`n")
  [void]$sb.Append("Cache-Control: no-store`r`nX-Content-Type-Options: nosniff`r`nVary: Origin`r`nConnection: close`r`n")
  if ($acao) { [void]$sb.Append("Access-Control-Allow-Origin: $acao`r`n") }
  if ($extra) { foreach ($k in $extra.Keys) { [void]$sb.Append("${k}: $($extra[$k])`r`n") } }
  [void]$sb.Append("`r`n")
  $head = [System.Text.Encoding]::ASCII.GetBytes($sb.ToString())
  $stream.Write($head, 0, $head.Length)
  if (-not $headOnly -and $bytes.Length -gt 0) { $stream.Write($bytes, 0, $bytes.Length) }
  $stream.Flush()
}

function Get-TmError([string]$err) { return (([ordered]@{ ok = $false; error = $err }) | ConvertTo-Json -Compress) }

function Read-TmHead($stream) {
  # Request line <= 2 KB and head <= 8 KB; anything larger -> 431. The body is never read.
  $ms = New-Object System.IO.MemoryStream
  $chunk = New-Object byte[] 2048
  while ($ms.Length -le 8192) {
    $n = $stream.Read($chunk, 0, $chunk.Length)
    if ($n -le 0) { return $null }
    $ms.Write($chunk, 0, $n)
    $text = [System.Text.Encoding]::ASCII.GetString($ms.ToArray())
    $end = $text.IndexOf("`r`n`r`n")
    if ($end -ge 0) {
      if ($end -gt 8192) { return 'too-big' }
      $h = $text.Substring(0, $end)
      $first = $h.IndexOf("`r`n")
      if ($first -lt 0) { $first = $h.Length }
      if ($first -gt 2048) { return 'too-big' }
      return $h
    }
  }
  return 'too-big'
}

function Invoke-TmClient($client) {
  $client.ReceiveTimeout = 3000
  $client.SendTimeout = 3000
  $stream = $client.GetStream()
  $head = Read-TmHead $stream
  if ($null -eq $head) { return }
  if ($head -eq 'too-big') { Send-TmResponse $stream 431 (Get-TmError 'too-large') $null $null $false; return }

  $lines = $head -split "`r`n"
  $req = $lines[0] -split ' '
  if ($req.Count -ne 3) { Send-TmResponse $stream 400 (Get-TmError 'bad-request') $null $null $false; return }
  $method = $req[0]
  $path = ($req[1] -split '\?', 2)[0]
  $hdr = @{}
  for ($i = 1; $i -lt $lines.Count; $i++) {
    $c = $lines[$i].IndexOf(':')
    if ($c -le 0) { continue }
    $name = $lines[$i].Substring(0, $c).Trim().ToLowerInvariant()
    $value = $lines[$i].Substring($c + 1).Trim()
    if ($hdr.ContainsKey($name) -and @('host', 'origin', 'x-fafo-tm-token') -contains $name) {
      Send-TmResponse $stream 400 (Get-TmError 'bad-request') $null $null $false; return
    }
    $hdr[$name] = $value
  }
  $headOnly = ($method -ceq 'HEAD')

  # 0: DNS-rebinding guard
  $hostH = [string]$hdr['host']
  if (-not ($hostH -eq "127.0.0.1:$Port" -or $hostH -eq "localhost:$Port")) {
    Send-TmResponse $stream 403 (Get-TmError 'bad-host') $null $null $headOnly; return
  }

  # Origin class: exact toolbox origin, 'null', none, or foreign. $allowed is always one of our constants.
  $hasOrigin = $hdr.ContainsKey('origin')
  $origin = [string]$hdr['origin']
  $allowed = $null
  foreach ($o in $ToolboxOrigins) { if ($origin -ceq $o) { $allowed = $o } }
  $isNull = ($hasOrigin -and $origin -ceq 'null')
  if ($isNull) { $allowed = 'null' }

  # 1: CORS preflight
  if ($method -ceq 'OPTIONS' -and $hdr.ContainsKey('access-control-request-method')) {
    if (-not $allowed) { Send-TmResponse $stream 403 (Get-TmError 'origin-forbidden') $null $null $false; return }
    $extra = [ordered]@{
      'Access-Control-Allow-Methods' = 'GET, OPTIONS'
      'Access-Control-Allow-Headers' = 'X-FAFO-TM-Token'
      'Access-Control-Max-Age'       = '600'
    }
    if ([string]$hdr['access-control-request-private-network'] -eq 'true') { $extra['Access-Control-Allow-Private-Network'] = 'true' }
    Send-TmResponse $stream 204 '' $allowed $extra $false; return
  }

  # 2: foreign origin -> 403, no ACAO, on every path
  if ($hasOrigin -and -not $allowed) { Send-TmResponse $stream 403 (Get-TmError 'origin-forbidden') $null $null $headOnly; return }

  # 3: methods
  if (-not ($method -ceq 'GET' -or $headOnly)) {
    Send-TmResponse $stream 405 (Get-TmError 'method-not-allowed') $null @{ 'Allow' = 'GET, HEAD, OPTIONS' } $false; return
  }

  # 4: /health (token-free, no paths; does not count as activity)
  if ($path -ceq '/health') {
    $h = [ordered]@{ ok = $true; service = 'fafo-transfer-helper'; schema = 1; readOnly = $true; port = $Port; pid = $PID }
    Send-TmResponse $stream 200 ($h | ConvertTo-Json -Compress) $allowed $null $headOnly; return
  }

  # 5: only /transfers beyond this point
  if (-not ($path -ceq '/transfers')) { Send-TmResponse $stream 404 (Get-TmError 'not-found') $null $null $headOnly; return }

  # 6-8: toolbox origin passes; Origin null and no-Origin need the token header
  if (-not ($allowed -and -not $isNull)) {
    if (-not (Test-TmToken ([string]$hdr['x-fafo-tm-token']))) {
      $acao = $null
      if ($isNull) { $acao = 'null' }
      Send-TmResponse $stream 403 (Get-TmError 'bad-token') $acao $null $headOnly; return
    }
  }
  $script:LastUse = Get-Date
  Invoke-Collect
  Send-TmResponse $stream 200 (ConvertTo-TmJson) $allowed $null $headOnly
}

# ---- single instance, bind, token file, serve until idle ----
$createdNew = $false
$mutex = [System.Threading.Mutex]::new($true, "Local\FAFOTransferMonitorHelper.$Port", [ref]$createdNew)
if (-not $createdNew) {
  $mutex.Dispose()
  [Console]::Out.WriteLine("already running on 127.0.0.1:$Port")
  exit 0
}

$exitCode = 0
$listener = $null
try {
  $bound = $false
  try {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    $listener.ExclusiveAddressUse = $true
    $listener.Start()
    $bound = $true
  } catch {
    [Console]::Error.WriteLine("cannot bind 127.0.0.1:${Port}: $($_.Exception.Message)")
    $exitCode = 3
  }
  if ($bound) {
    Write-TmTokenFile
    Invoke-Collect   # warm-up before serving: the first Get-BitsTransfer (~4.3 s cold) leaves the first request
    $script:LastUse = Get-Date
    $idle = [TimeSpan]::FromMinutes($IdleMinutes)
    while (((Get-Date) - $script:LastUse) -lt $idle) {
      if (-not $listener.Pending()) { Start-Sleep -Milliseconds 50; continue }
      $client = $listener.AcceptTcpClient()
      try { Invoke-TmClient $client } catch {} finally { $client.Close() }
    }
  }
} finally {
  if ($listener) { try { $listener.Stop() } catch {} }
  Remove-TmTokenFile
  try { $mutex.ReleaseMutex() } catch {}
  $mutex.Dispose()
}
exit $exitCode
