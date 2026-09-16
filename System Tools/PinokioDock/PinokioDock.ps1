#requires -Version 5.1
<#
.SYNOPSIS
  FAFO Dockwatcher — dark dock, cycle apps, live FlashVSR queue board.

.DESCRIPTION
  - Launch Pinokio desktop app only (never opens C:\pinokio\api folders)
  - Cycle app selection without stealing focus / without Explorer
  - Realtime FlashVSR queues + watch-folder depth badges (1,5,10,25,50,100…)
  - Profiles for webui_config field persistence
#>
param(
  [string]$PinokioHome = 'C:\pinokio',
  [string]$DataDir = "$env:LOCALAPPDATA\FAFO\PinokioDock",
  [string]$FlashVsrApp = 'C:\pinokio\api\FlashVSR_plus_pinokio.git\app',
  [switch]$StartMinimized,
  [switch]$PinOnTop
)

$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

try {
  Add-Type -Namespace PkDock -Name Win32 -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern System.IntPtr GetConsoleWindow();
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool SetWindowPos(System.IntPtr hWnd, System.IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern System.IntPtr GetForegroundWindow();
[System.Runtime.InteropServices.DllImport("dwmapi.dll")]
public static extern int DwmSetWindowAttribute(System.IntPtr hwnd, int attr, ref int attrValue, int attrSize);
'@ -ErrorAction Stop
  $c = [PkDock.Win32]::GetConsoleWindow()
  if ($c -ne [System.IntPtr]::Zero) { [void][PkDock.Win32]::ShowWindow($c, 0) }
} catch {}

function Enable-DarkTitleBar([System.Windows.Forms.Form]$f) {
  # Windows 10 1809+ / 11 immersive dark title bar
  if (-not $f -or -not $f.IsHandleCreated) { return }
  try {
    $useDark = 1
    # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win10 20H1+), 19 on some builds
    [void][PkDock.Win32]::DwmSetWindowAttribute($f.Handle, 20, [ref]$useDark, 4)
    [void][PkDock.Win32]::DwmSetWindowAttribute($f.Handle, 19, [ref]$useDark, 4)
  } catch {}
}

function Set-PinNoActivate([System.Windows.Forms.Form]$f, [bool]$pin) {
  if (-not $f) { return }
  try {
    if (-not $f.IsHandleCreated) { $f.TopMost = $pin; return }
    $after = if ($pin) { [IntPtr](-1) } else { [IntPtr](-2) }
    $flags = [uint32](0x0001 -bor 0x0002 -bor 0x0010) # NOSIZE|NOMOVE|NOACTIVATE
    [void][PkDock.Win32]::SetWindowPos($f.Handle, $after, 0, 0, 0, 0, $flags)
    $f.TopMost = $pin
  } catch { $f.TopMost = $pin }
}

# --- theme ---
$T = @{
  Bg     = [Drawing.Color]::FromArgb(5, 5, 8)
  Panel  = [Drawing.Color]::FromArgb(10, 14, 18)
  Panel2 = [Drawing.Color]::FromArgb(14, 18, 24)
  Accent = [Drawing.Color]::FromArgb(0, 243, 255)
  Text   = [Drawing.Color]::FromArgb(230, 245, 250)
  Muted  = [Drawing.Color]::FromArgb(110, 140, 150)
  Ok     = [Drawing.Color]::FromArgb(80, 255, 200)
  Bad    = [Drawing.Color]::FromArgb(255, 120, 120)
  Warn   = [Drawing.Color]::FromArgb(255, 200, 80)
  Run    = [Drawing.Color]::FromArgb(120, 200, 255)
  Btn    = [Drawing.Color]::FromArgb(8, 22, 28)
  ChipOn = [Drawing.Color]::FromArgb(0, 60, 70)
  ChipOff= [Drawing.Color]::FromArgb(20, 24, 28)
}

New-Item -ItemType Directory -Force -Path $DataDir, (Join-Path $DataDir 'profiles') | Out-Null
$DockPath = Join-Path $DataDir 'dock.json'
$LogPath  = Join-Path $DataDir 'dock.log'
$TierSteps = @(1, 5, 10, 25, 50, 100, 250, 500, 1000)

function Write-DockLog([string]$m) {
  try { Add-Content $LogPath ("{0:u} {1}" -f (Get-Date), $m) -Encoding UTF8 } catch {}
}

function Get-PtermPath {
  foreach ($c in @(
    (Join-Path $PinokioHome 'bin\npm\pterm.cmd'),
    (Join-Path $PinokioHome 'bin\npm\pterm'),
    (Join-Path $PinokioHome 'bin\pterm.cmd')
  )) {
    if (Test-Path -LiteralPath $c) { return $c }
  }
  return $null
}

function Get-PinokioExe {
  foreach ($c in @(
    "$env:LOCALAPPDATA\Programs\Pinokio\Pinokio.exe",
    "$env:LOCALAPPDATA\Pinokio\Pinokio.exe"
  )) {
    if (Test-Path -LiteralPath $c) { return $c }
  }
  foreach ($lnk in @(
    "$env:USERPROFILE\Desktop\Pinokio.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Pinokio.lnk"
  )) {
    if (-not (Test-Path -LiteralPath $lnk)) { continue }
    try {
      $sh = New-Object -ComObject WScript.Shell
      $sc = $sh.CreateShortcut($lnk)
      if ($sc.TargetPath -and (Test-Path -LiteralPath $sc.TargetPath)) { return $sc.TargetPath }
    } catch {}
  }
  return $null
}

function Test-PinokioProcess {
  return $null -ne (Get-Process -Name 'Pinokio' -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Test-PinokioControlPlane([int]$TimeoutMs = 600) {
  $hosts = @('127.0.0.1')
  $cfgPath = Join-Path $env:USERPROFILE '.pinokio\config.json'
  if (Test-Path $cfgPath) {
    try {
      $cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
      if ($cfg.access.host) { $hosts = @([string]$cfg.access.host) + $hosts }
    } catch {}
  }
  foreach ($h in ($hosts | Select-Object -Unique)) {
    try {
      $req = [Net.HttpWebRequest]::Create("http://${h}:42000/")
      $req.Method = 'GET'; $req.Timeout = $TimeoutMs; $req.ReadWriteTimeout = $TimeoutMs
      $resp = $req.GetResponse(); $resp.Close()
      return @{ ok = $true; url = "http://${h}:42000" }
    } catch {}
  }
  return @{ ok = $false }
}

function Invoke-Pterm([string[]]$PtermArgs, [int]$TimeoutSec = 15) {
  $pterm = Get-PtermPath
  if (-not $pterm) { return @{ ok = $false; error = 'pterm not found' } }
  try {
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $pterm
    $psi.Arguments = ($PtermArgs | ForEach-Object {
      if ($_ -match '[\s"]') { '"{0}"' -f ($_ -replace '"', '\"') } else { $_ }
    }) -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $p = [Diagnostics.Process]::Start($psi)
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
      try { $p.Kill() } catch {}
      return @{ ok = $false; error = 'pterm timeout' }
    }
    return @{
      ok   = ($p.ExitCode -eq 0)
      code = $p.ExitCode
      out  = $p.StandardOutput.ReadToEnd()
      err  = $p.StandardError.ReadToEnd()
    }
  } catch {
    return @{ ok = $false; error = $_.Exception.Message }
  }
}

function Start-PinokioDesktop([switch]$WaitReady, [int]$WaitSec = 40) {
  $exe = Get-PinokioExe
  if (-not $exe) {
    Set-Status 'Pinokio.exe not found' 'bad'
    return $false
  }
  # ONLY launch the desktop app — never Explorer, never api folder
  if (-not (Test-PinokioProcess)) {
    Set-Status 'Starting Pinokio desktop...' 'accent'
    Start-Process -FilePath $exe
    Write-DockLog "Start-Process $exe"
  } else {
    Set-Status 'Pinokio already running' 'ok'
    # Do NOT re-launch in a way that opens folders; optional soft focus via exe only
    try { Start-Process -FilePath $exe } catch {}
  }
  if (-not $WaitReady) { return $true }
  $deadline = (Get-Date).AddSeconds($WaitSec)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 700
    try { [Windows.Forms.Application]::DoEvents() } catch {}
    if ((Test-PinokioProcess) -and (Test-PinokioControlPlane).ok) {
      Set-Status 'Pinokio control plane online' 'ok'
      return $true
    }
    Set-Status 'Waiting for Pinokio API (no folder opens)...' 'accent'
  }
  if (Test-PinokioProcess) {
    Set-Status 'Pinokio process up (API may still be warming)' 'ok'
    return $true
  }
  Set-Status 'Pinokio did not start' 'bad'
  return $false
}

# --- dock favorites ---
function Load-Dock {
  if (Test-Path $DockPath) {
    try { return Get-Content $DockPath -Raw | ConvertFrom-Json } catch {}
  }
  $cycle = @()
  $api = Join-Path $PinokioHome 'api'
  if (Test-Path $api) {
    Get-ChildItem $api -Directory | Sort-Object Name | ForEach-Object {
      $cycle += [pscustomobject]@{ id = $_.Name; label = ($_.Name -replace '\.git$', ''); path = $_.FullName }
    }
  }
  return [pscustomobject]@{ version = 2; pinokio_home = $PinokioHome; cycle = $cycle; index = 0 }
}
function Save-Dock($d) { ($d | ConvertTo-Json -Depth 8) | Set-Content $DockPath -Encoding UTF8 }

function Get-InstalledApps {
  $api = Join-Path $PinokioHome 'api'
  $list = @()
  if (Test-Path $api) {
    Get-ChildItem $api -Directory | Sort-Object Name | ForEach-Object {
      $list += [pscustomobject]@{ id = $_.Name; label = ($_.Name -replace '\.git$', ''); path = $_.FullName }
    }
  }
  return $list
}

# --- FlashVSR realtime ---
function Get-QueueSnapshot([string]$name) {
  $qpath = Join-Path $FlashVsrApp "outputs\work_queue_$name\queue.json"
  $spath = Join-Path $FlashVsrApp "outputs\work_queue_$name\STATUS.txt"
  $stop  = Join-Path $FlashVsrApp "outputs\work_queue_$name\STOP_AFTER_CURRENT.flag"
  $result = [ordered]@{
    name         = $name
    total        = 0
    pending      = 0
    running      = 0
    done         = 0
    failed       = 0
    stop         = (Test-Path $stop)
    status       = ''
    path         = $qpath
    updated      = ''
    run_started  = ''
    completed_dir = ''
    current_name = ''
    current_path = ''
    current_index = 0
    current_attempts = 0
    current_error = ''
    # 0-100 overall: finished (done+failed) / total; when running, nudge slightly
    pct_overall  = 0
    # 0-100 "this pass" among remaining work: done / (done+pending+running)
    pct_step     = 0
    step_label   = 'idle'
    phase        = 'idle'   # idle | running | done | failed-mix
  }
  if (Test-Path $qpath) {
    try {
      $raw = [System.IO.File]::ReadAllText($qpath)
      $data = $raw | ConvertFrom-Json
      $result.updated = [string]$data.updated
      $result.run_started = [string]$data.run_started
      $result.completed_dir = [string]$data.completed_dir
      $idx = 0
      $runItem = $null
      $runIdx = 0
      foreach ($it in @($data.items)) {
        $idx++
        $result.total++
        switch ($it.status) {
          'pending' { $result.pending++ }
          'running' {
            $result.running++
            if (-not $runItem) { $runItem = $it; $runIdx = $idx }
          }
          'done'    { $result.done++ }
          'failed'  { $result.failed++ }
          default   { $result.pending++ }
        }
      }
      if ($runItem) {
        $p = [string]$runItem.path
        $result.current_path = $p
        $result.current_name = [IO.Path]::GetFileName($p)
        $result.current_index = $runIdx
        $result.current_attempts = [int]$(if ($runItem.attempts) { $runItem.attempts } else { 0 })
        $result.current_error = [string]$runItem.error
        $result.phase = 'running'
        $tryPart = if ($result.current_attempts -gt 0) { " try $($result.current_attempts)" } else { '' }
        $gtStage = [string]$data.gt_current_stage
        $gtGroup = [string]$data.gt_current_group
        if ($name -eq 'group' -and $gtStage) {
          $result.step_label = "G$gtGroup $gtStage$tryPart · $($result.current_name)"
        } else {
          $result.step_label = "RUN #$runIdx/$($result.total)$tryPart · $($result.current_name)"
        }
      } elseif ($result.total -gt 0 -and $result.pending -eq 0 -and $result.running -eq 0) {
        $result.phase = 'done'
        $result.step_label = "complete · done $($result.done) · fail $($result.failed)"
      } elseif ($result.pending -gt 0) {
        $result.phase = 'waiting'
        $result.step_label = "WAIT $($result.pending) · done $($result.done)/$($result.total)"
      } else {
        $result.phase = 'idle'
        $result.step_label = 'idle'
      }

      if ($result.total -gt 0) {
        $finished = $result.done + $result.failed
        $result.pct_overall = [int][Math]::Min(100, [Math]::Floor(100.0 * $finished / $result.total))
        # While a job is running, show partial progress into next slot
        if ($result.running -gt 0) {
          $result.pct_overall = [int][Math]::Min(99, $result.pct_overall + [Math]::Floor(100.0 / $result.total / 2))
        }
        $activePool = $result.done + $result.pending + $result.running
        if ($activePool -gt 0) {
          $stepDone = $result.done
          if ($result.running -gt 0) { $stepDone = $result.done } # bar fills on complete only
          $result.pct_step = [int][Math]::Min(100, [Math]::Floor(100.0 * $stepDone / $activePool))
          if ($result.running -gt 0 -and $result.pct_step -lt 99) {
            # pulse mid-step so bar is visibly "working"
            $tick = [Environment]::TickCount
            $pulse = [int](8 + (6 * [Math]::Sin($tick / 180.0)))
            $result.pct_step = [int][Math]::Min(99, $result.pct_step + $pulse)
          }
        }
      }
    } catch {}
  }
  if (Test-Path $spath) {
    try {
      $lines = Get-Content -LiteralPath $spath -TotalCount 12 -ErrorAction SilentlyContinue
      $result.status = ($lines -join ' | ')
      # Prefer first RUN line from STATUS for step label if richer
      foreach ($ln in $lines) {
        if ($ln -match '^\s*\[RUN') {
          $result.step_label = ($ln.Trim() -replace '\s+', ' ')
          break
        }
      }
    } catch {}
  }
  return [pscustomobject]$result
}

function Format-AsciiBar([int]$pct, [int]$width = 18) {
  if ($pct -lt 0) { $pct = 0 }
  if ($pct -gt 100) { $pct = 100 }
  $filled = [int][Math]::Round($width * $pct / 100.0)
  if ($filled -gt $width) { $filled = $width }
  $empty = $width - $filled
  return ('[{0}{1}] {2,3}%' -f ('█' * $filled), ('░' * $empty), $pct)
}

$script:FolderCountCache = @{}  # path -> @{ n=; at= }

function Get-FolderFileCount([string]$path, [int]$CacheSec = 12) {
  if (-not $path -or -not (Test-Path -LiteralPath $path)) { return 0 }
  $now = [Environment]::TickCount
  if ($script:FolderCountCache.ContainsKey($path)) {
    $hit = $script:FolderCountCache[$path]
    if (($now - [int]$hit.at) -lt ($CacheSec * 1000)) { return [int]$hit.n }
  }
  try {
    # Fast enumeration — count files only, no metadata sort
    $n = 0
    foreach ($f in [System.IO.Directory]::EnumerateFiles($path)) { $n++ }
    $script:FolderCountCache[$path] = @{ n = $n; at = $now }
    return $n
  } catch {
    try {
      $n = @(Get-ChildItem -LiteralPath $path -File -Force -ErrorAction SilentlyContinue).Count
      $script:FolderCountCache[$path] = @{ n = $n; at = $now }
      return $n
    } catch { return 0 }
  }
}

function Read-KeyValueFile([string]$path) {
  $h = [ordered]@{}
  if (-not (Test-Path $path)) { return $h }
  Get-Content -LiteralPath $path | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
      $k, $v = $line.Split('=', 2)
      $h[$k.Trim()] = $v.Trim()
    }
  }
  return $h
}

function Get-WatchFolders {
  $cfg = Join-Path $FlashVsrApp 'webui_config'
  $map = Read-KeyValueFile $cfg
  return [ordered]@{
    'Inbox (NEW)'     = $(if ($map.batch_watch_folder) { $map.batch_watch_folder } else { 'D:\OUTPUTS\__X_GROK\NEW DOWNLOADS' })
    'Pre Scaled'      = $(if ($map.batch_source_archive_dir) { $map.batch_source_archive_dir } else { 'D:\OUTPUTS\__X_GROK\Upscaled Videos\Pre Scaled videos' })
    'Ready Toolbox'   = $(if ($map.batch_upscale_handoff_dir) { $map.batch_upscale_handoff_dir } else { 'D:\OUTPUTS\__X_GROK\Upscaled Videos\Ready for Toolbox' })
    'Ready CIV'       = $(if ($map.toolbox_output_dir) { $map.toolbox_output_dir } else { 'D:\OUTPUTS\__X_GROK\Upscaled Videos\Post Scaling\Ready for CIV' })
  }
}

function Get-TierActive([int]$count) {
  # which badge steps are "lit" for this count
  $on = @{}
  foreach ($t in $TierSteps) { $on[$t] = ($count -ge $t) }
  return $on
}

function Format-TierLine([int]$count) {
  $parts = @()
  foreach ($t in $TierSteps) {
    if ($count -ge $t) { $parts += "[$t]" } else { $parts += " $t " }
  }
  return ("{0,5}  {1}" -f $count, ($parts -join ''))
}

function Format-QueueBlock([string]$title, $snap) {
  if (-not $snap) {
    return @"
$title
  (no queue.json yet)
  bar: $(Format-AsciiBar 0)
  badges: $(Format-TierLine 0)

"@
  }
  $stop = if ($snap.stop) { '  STOP-AFTER' } else { '' }
  $pending = [int]$snap.pending
  $bar = Format-AsciiBar ([int]$snap.pct_overall)
  $step = Format-AsciiBar ([int]$snap.pct_step) 14
  $cur = if ($snap.step_label) { $snap.step_label } else { 'idle' }
  return @"
$($title.ToUpper())$stop
  total $($snap.total)   RUN $($snap.running)   WAIT $pending   DONE $($snap.done)   FAIL $($snap.failed)
  overall $bar
  step    $step  $cur
  wait-depth badges: $(Format-TierLine $pending)

"@
}

# --- profiles (FlashVSR config) ---
function Get-FlashVsrConfigPath {
  $p = Join-Path $FlashVsrApp 'webui_config'
  if (Test-Path $p) { return $p }
  return $null
}
function Write-KeyValueFile([string]$path, $map) {
  $lines = @(); foreach ($k in $map.Keys) { $lines += "$k=$($map[$k])" }
  if (Test-Path $path) { Copy-Item $path ($path + '.bak') -Force }
  Set-Content -LiteralPath $path -Value ($lines -join "`n") -Encoding UTF8
}
function Save-ProfileFromFlashVsr([string]$name) {
  $cfg = Get-FlashVsrConfigPath
  if (-not $cfg) { throw 'webui_config missing' }
  $settings = Read-KeyValueFile $cfg
  $id = ($name.ToLower() -replace '[^a-z0-9]+', '-').Trim('-')
  $obj = [ordered]@{ id = $id; name = $name; kind = 'webui_config'; saved_at = (Get-Date).ToString('o'); settings = $settings }
  $out = Join-Path $DataDir "profiles\$id.json"
  ($obj | ConvertTo-Json -Depth 8) | Set-Content $out -Encoding UTF8
  return $out
}
function Apply-Profile([string]$profilePath) {
  $p = Get-Content $profilePath -Raw | ConvertFrom-Json
  $cfg = Get-FlashVsrConfigPath
  if (-not $cfg) { throw 'webui_config missing' }
  $map = [ordered]@{}
  $p.settings.PSObject.Properties | ForEach-Object { $map[$_.Name] = [string]$_.Value }
  Write-KeyValueFile $cfg $map
  return "Applied '$($p.name)' → reload FlashVSR UI"
}
function Get-Profiles {
  Get-ChildItem (Join-Path $DataDir 'profiles') -Filter '*.json' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending
}

# --- state ---
$script:Dock = Load-Dock
if (-not $script:Dock.PSObject.Properties['index']) {
  $script:Dock | Add-Member -NotePropertyName index -NotePropertyValue 0 -Force
}
$script:Cycle = @($script:Dock.cycle)
if (-not $script:Cycle -or $script:Cycle.Count -eq 0) {
  $script:Cycle = @(Get-InstalledApps)
  $script:Dock.cycle = $script:Cycle
  Save-Dock $script:Dock
}
if ($script:Dock.index -ge $script:Cycle.Count) { $script:Dock.index = 0 }

function Current-App {
  if ($script:Cycle.Count -eq 0) { return $null }
  return $script:Cycle[$script:Dock.index]
}

# --- UI ---
$form = New-Object Windows.Forms.Form
$form.Text = 'FAFO Dockwatcher'
$form.Size = New-Object Drawing.Size(960, 640)
$form.MinimumSize = New-Object Drawing.Size(800, 500)
$form.StartPosition = 'Manual'
$form.Location = New-Object Drawing.Point(36, 36)
$form.BackColor = $T.Bg
$form.ForeColor = $T.Text
$form.FormBorderStyle = 'Sizable'
$form.ShowInTaskbar = $true
$form.TopMost = $false
$form.Font = New-Object Drawing.Font('Segoe UI', 9)
# Dark chrome as soon as handle exists
$form.Add_HandleCreated({ Enable-DarkTitleBar $form })
$form.Add_Shown({ Enable-DarkTitleBar $form })

function Set-Status([string]$text, [string]$kind = 'muted') {
  if (-not $script:lblStatus) { return }
  $script:lblStatus.Text = $text
  $script:lblStatus.ForeColor = switch ($kind) {
    'ok' { $T.Ok }; 'bad' { $T.Bad }; 'accent' { $T.Accent }; 'warn' { $T.Warn }; default { $T.Muted }
  }
}

# top bar
$top = New-Object Windows.Forms.Panel
$top.Dock = 'Top'
$top.Height = 108
$top.BackColor = $T.Panel
$form.Controls.Add($top)

$lblTitle = New-Object Windows.Forms.Label
$lblTitle.Text = 'FAFO DOCKWATCHER'
$lblTitle.ForeColor = $T.Accent
$lblTitle.Font = New-Object Drawing.Font('Segoe UI Semibold', 11)
$lblTitle.Location = New-Object Drawing.Point(12, 8)
$lblTitle.AutoSize = $true
$top.Controls.Add($lblTitle)

$chkPin = New-Object Windows.Forms.CheckBox
$chkPin.Text = 'Pin (no focus steal)'
$chkPin.ForeColor = $T.Accent
$chkPin.AutoSize = $true
$chkPin.Location = New-Object Drawing.Point(160, 10)
$chkPin.Checked = [bool]$PinOnTop
$chkPin.Add_CheckedChanged({ Set-PinNoActivate $form $chkPin.Checked })
$top.Controls.Add($chkPin)

$chkAutoOpen = New-Object Windows.Forms.CheckBox
$chkAutoOpen.Text = 'Auto-open app UI on cycle (off = safer)'
$chkAutoOpen.ForeColor = $T.Muted
$chkAutoOpen.AutoSize = $true
$chkAutoOpen.Location = New-Object Drawing.Point(340, 10)
$chkAutoOpen.Checked = $false  # default OFF — was causing folder opens / focus steal
$top.Controls.Add($chkAutoOpen)

$lblApp = New-Object Windows.Forms.Label
$lblApp.ForeColor = $T.Text
$lblApp.Font = New-Object Drawing.Font('Segoe UI Semibold', 11)
$lblApp.Location = New-Object Drawing.Point(12, 34)
$lblApp.Size = New-Object Drawing.Size(860, 22)
$top.Controls.Add($lblApp)

function New-DockBtn([string]$text, [int]$x, [int]$w = 88) {
  $b = New-Object Windows.Forms.Button
  $b.Text = $text
  $b.Location = New-Object Drawing.Point($x, 62)
  $b.Size = New-Object Drawing.Size($w, 30)
  $b.FlatStyle = 'Flat'
  $b.FlatAppearance.BorderColor = $T.Accent
  $b.BackColor = $T.Btn
  $b.ForeColor = $T.Accent
  return $b
}

$btnPinokio = New-DockBtn 'Launch Pinokio' 12 110
$btnPrev    = New-DockBtn '◀ Prev' 130 70
$btnNext    = New-DockBtn 'Next ▶' 206 70
$btnOpen    = New-DockBtn 'Open UI' 282 70
$btnRun     = New-DockBtn 'Run app' 358 70
$btnSave    = New-DockBtn 'Save fields' 434 88
$btnApply   = New-DockBtn 'Apply profile' 528 96
$btnRefresh = New-DockBtn 'Refresh data' 630 96
$top.Controls.AddRange(@($btnPinokio, $btnPrev, $btnNext, $btnOpen, $btnRun, $btnSave, $btnApply, $btnRefresh))

$cboProfile = New-Object Windows.Forms.ComboBox
$cboProfile.DropDownStyle = 'DropDownList'
$cboProfile.Location = New-Object Drawing.Point(734, 64)
$cboProfile.Size = New-Object Drawing.Size(140, 28)
$cboProfile.BackColor = $T.Bg
$cboProfile.ForeColor = $T.Text
$top.Controls.Add($cboProfile)

# status
$script:lblStatus = New-Object Windows.Forms.Label
$script:lblStatus.Dock = 'Bottom'
$script:lblStatus.Height = 22
$script:lblStatus.ForeColor = $T.Muted
$script:lblStatus.Padding = New-Object Windows.Forms.Padding(10, 2, 0, 0)
$script:lblStatus.Text = 'Ready'
$form.Controls.Add($script:lblStatus)

# main split: queues | live status
$split = New-Object Windows.Forms.SplitContainer
$split.Dock = 'Fill'
$split.Orientation = 'Horizontal'
$split.SplitterDistance = 300
$split.BackColor = $T.Bg
$form.Controls.Add($split)
$form.Controls.SetChildIndex($split, 0)

# QUEUE panel header
$lblQ = New-Object Windows.Forms.Label
$lblQ.Text = 'FAFO QUEUES  ·  LIVE STEP BARS  ·  DEPTH BADGES  [1][5][10][25][50][100]…'
$lblQ.Dock = 'Top'
$lblQ.Height = 24
$lblQ.ForeColor = $T.Accent
$lblQ.Font = New-Object Drawing.Font('Segoe UI Semibold', 9)
$lblQ.Padding = New-Object Windows.Forms.Padding(10, 4, 0, 0)
$lblQ.BackColor = $T.Panel2
$split.Panel1.Controls.Add($lblQ)

# --- Visual progress bars (one row per queue step) ---
$pnlBars = New-Object Windows.Forms.Panel
$pnlBars.Dock = 'Top'
$pnlBars.Height = 144
$pnlBars.BackColor = $T.Panel
$pnlBars.Padding = New-Object Windows.Forms.Padding(8, 4, 8, 4)
$split.Panel1.Controls.Add($pnlBars)

function New-QueueBarRow([string]$key, [string]$title, [int]$y) {
  $lbl = New-Object Windows.Forms.Label
  $lbl.Text = $title
  $lbl.ForeColor = $T.Accent
  $lbl.Font = New-Object Drawing.Font('Segoe UI Semibold', 8.5)
  $lbl.Location = New-Object Drawing.Point(8, $y)
  $lbl.Size = New-Object Drawing.Size(78, 16)
  $pnlBars.Controls.Add($lbl)

  $bar = New-Object Windows.Forms.ProgressBar
  $bar.Location = New-Object Drawing.Point(90, ($y - 1))
  $bar.Size = New-Object Drawing.Size(360, 18)
  $bar.Minimum = 0
  $bar.Maximum = 100
  $bar.Value = 0
  $bar.Style = 'Continuous'
  $pnlBars.Controls.Add($bar)

  $pct = New-Object Windows.Forms.Label
  $pct.Text = '0%'
  $pct.ForeColor = $T.Ok
  $pct.Font = New-Object Drawing.Font('Consolas', 9)
  $pct.Location = New-Object Drawing.Point(456, $y)
  $pct.Size = New-Object Drawing.Size(48, 16)
  $pnlBars.Controls.Add($pct)

  $detail = New-Object Windows.Forms.Label
  $detail.Text = 'idle'
  $detail.ForeColor = $T.Muted
  $detail.Font = New-Object Drawing.Font('Segoe UI', 8)
  $detail.Location = New-Object Drawing.Point(508, $y)
  $detail.Size = New-Object Drawing.Size(380, 16)
  $detail.AutoEllipsis = $true
  $pnlBars.Controls.Add($detail)

  return @{ key = $key; bar = $bar; pct = $pct; detail = $detail; title = $lbl }
}

$script:BarRows = @{
  video   = (New-QueueBarRow 'video'   'VIDEO'   6)
  image   = (New-QueueBarRow 'image'   'IMAGE'   30)
  toolbox = (New-QueueBarRow 'toolbox' 'TOOLBOX' 54)
  group   = (New-QueueBarRow 'group'   'GROUP'   78)
  folders = (New-QueueBarRow 'folders' 'FOLDERS' 102)
}
# folder bar uses sum of watch depths as a soft indicator
$script:BarRows.folders.detail.Text = 'watch-folder depth (aggregate)'

function Set-QueueBarRow($row, $snap) {
  if (-not $row) { return }
  $pct = 0
  $detail = 'idle'
  $color = $T.Muted
  if ($snap) {
    $pct = [int]$snap.pct_overall
    if ($pct -lt 0) { $pct = 0 }
    if ($pct -gt 100) { $pct = 100 }
    $detail = [string]$snap.step_label
    if (-not $detail) { $detail = 'idle' }
    switch ($snap.phase) {
      'running' { $color = $T.Run }
      'done'    { $color = $T.Ok }
      'waiting' { $color = $T.Warn }
      default   { $color = $T.Muted }
    }
    if ($snap.stop) { $detail = "STOP-AFTER · $detail" }
  }
  try {
    if ($row.bar.Value -ne $pct) { $row.bar.Value = $pct }
  } catch {
    try { $row.bar.Value = [Math]::Max(0, [Math]::Min(100, $pct)) } catch {}
  }
  $row.pct.Text = ('{0}%' -f $pct)
  $row.pct.ForeColor = $color
  $row.detail.Text = $detail
  $row.detail.ForeColor = $color
  $row.title.ForeColor = if ($snap -and $snap.phase -eq 'running') { $T.Run } else { $T.Accent }
}

function Set-FolderBarRow($row, $folders) {
  if (-not $row) { return }
  $sum = 0
  $parts = @()
  foreach ($name in @($folders.Keys)) {
    $c = [int]$folders[$name]
    $sum += $c
    $parts += ('{0}:{1}' -f $name, $c)
  }
  # Soft log-ish scale so 0-1000 maps into the bar
  $pct = 0
  if ($sum -gt 0) {
    $pct = [int][Math]::Min(100, [Math]::Round(20 * [Math]::Log10($sum + 1)))
  }
  try { $row.bar.Value = $pct } catch {}
  $row.pct.Text = ('{0}' -f $sum)
  $row.pct.ForeColor = if ($sum -gt 0) { $T.Ok } else { $T.Muted }
  $row.detail.Text = if ($parts.Count) { ($parts -join '  ·  ') } else { 'no watch folders' }
  $row.detail.ForeColor = $T.Muted
}

$txtMain = New-Object Windows.Forms.TextBox
$txtMain.Dock = 'Fill'
$txtMain.Multiline = $true
$txtMain.ScrollBars = 'Vertical'
$txtMain.ReadOnly = $true
# Force dark fill after ReadOnly (WinForms otherwise keeps system light Control color)
$txtMain.BackColor = $T.Bg
$txtMain.ForeColor = $T.Text
$txtMain.Font = New-Object Drawing.Font('Consolas', 9.5)
$txtMain.BorderStyle = 'FixedSingle'
$txtMain.WordWrap = $false
$txtMain.Text = 'Loading FAFO queue board...'
$split.Panel1.BackColor = $T.Bg
$split.Panel1.Controls.Add($txtMain)
$split.Panel1.Controls.SetChildIndex($txtMain, 0)

$script:QueuePaint = @{
  video = $null; image = $null; toolbox = $null; group = $null
  folders = [ordered]@{}
  exclusive = ''
  tick = 0
  lastFolderScan = 0
  lastUiMs = 0
}

# LIVE status text
$lblLive = New-Object Windows.Forms.Label
$lblLive.Text = 'LIVE STATUS.TXT  (FlashVSR output)'
$lblLive.Dock = 'Top'
$lblLive.Height = 24
$lblLive.ForeColor = $T.Accent
$lblLive.Font = New-Object Drawing.Font('Segoe UI Semibold', 9)
$lblLive.Padding = New-Object Windows.Forms.Padding(10, 4, 0, 0)
$lblLive.BackColor = $T.Panel2
$split.Panel2.Controls.Add($lblLive)

$txtLive = New-Object Windows.Forms.TextBox
$txtLive.Dock = 'Fill'
$txtLive.Multiline = $true
$txtLive.ScrollBars = 'Vertical'
$txtLive.ReadOnly = $true
$txtLive.BackColor = $T.Bg
$txtLive.ForeColor = $T.Ok
$txtLive.Font = New-Object Drawing.Font('Consolas', 9)
$txtLive.BorderStyle = 'FixedSingle'
$txtLive.WordWrap = $false
$split.Panel2.BackColor = $T.Bg
$split.Panel2.Controls.Add($txtLive)
$split.Panel2.Controls.SetChildIndex($txtLive, 0)
# Re-assert dark colors after handle create (ReadOnly can flash system light bg)
$form.Add_Shown({
  $txtMain.BackColor = $T.Bg
  $txtMain.ForeColor = $T.Text
  $txtLive.BackColor = $T.Bg
  $txtLive.ForeColor = $T.Ok
  $cboProfile.BackColor = $T.Bg
  $cboProfile.ForeColor = $T.Text
})

# --- logic ---
function Refresh-AppLabel {
  $app = Current-App
  if (-not $app) { $lblApp.Text = '(no apps in cycle list)'; return }
  $lblApp.Text = ("{0}/{1}  {2}" -f ($script:Dock.index + 1), $script:Cycle.Count, $app.label)
}

function Refresh-ProfileCombo {
  $cboProfile.Items.Clear()
  foreach ($f in Get-Profiles) {
    try {
      $j = Get-Content $f.FullName -Raw | ConvertFrom-Json
      [void]$cboProfile.Items.Add([pscustomobject]@{ Text = $(if ($j.name) { $j.name } else { $f.BaseName }); Path = $f.FullName })
    } catch {
      [void]$cboProfile.Items.Add([pscustomobject]@{ Text = $f.BaseName; Path = $f.FullName })
    }
  }
  $cboProfile.DisplayMember = 'Text'
  if ($cboProfile.Items.Count -gt 0) { $cboProfile.SelectedIndex = 0 }
}

function Refresh-LiveData {
  # NEVER open windows / folders / Activate here
  $t0 = [Environment]::TickCount
  $v = Get-QueueSnapshot 'video'
  $i = Get-QueueSnapshot 'image'
  $tb = Get-QueueSnapshot 'toolbox'
  $g = Get-QueueSnapshot 'group'
  $script:QueuePaint.video = $v
  $script:QueuePaint.image = $i
  $script:QueuePaint.toolbox = $tb
  $script:QueuePaint.group = $g

  # Progress bars update every tick (fast path)
  Set-QueueBarRow $script:BarRows.video $v
  Set-QueueBarRow $script:BarRows.image $i
  Set-QueueBarRow $script:BarRows.toolbox $tb
  Set-QueueBarRow $script:BarRows.group $g

  $lockPath = Join-Path $FlashVsrApp 'outputs\ACTIVE_QUEUE.lock'
  if (-not (Test-Path $lockPath)) {
    $lockPath = Join-Path $FlashVsrApp 'outputs\exclusive_queue_lock.json'
  }
  if (-not (Test-Path $lockPath)) {
    $alt = Get-ChildItem (Join-Path $FlashVsrApp 'outputs') -Filter '*lock*' -ErrorAction SilentlyContinue |
      Select-Object -First 1 -ExpandProperty FullName
    if ($alt) { $lockPath = $alt }
  }
  if (Test-Path $lockPath) {
    try {
      $lk = Get-Content $lockPath -Raw | ConvertFrom-Json
      $who = if ($lk.label) { $lk.label } elseif ($lk.queue) { $lk.queue } else { 'queue' }
      $pidv = if ($lk.pid) { $lk.pid } else { '?' }
      $started = if ($lk.started) { $lk.started } else { '' }
      $script:QueuePaint.exclusive = "ACTIVE LOCK: $who  pid $pidv  $started"
    } catch {
      $script:QueuePaint.exclusive = 'ACTIVE LOCK: (present)'
    }
  } else {
    $script:QueuePaint.exclusive = 'No exclusive queue lock — free to start a queue'
  }

  # Folder counts are expensive on big dirs — refresh every ~8s only
  $now = [Environment]::TickCount
  if (($now - [int]$script:QueuePaint.lastFolderScan) -gt 8000 -or $script:QueuePaint.folders.Count -eq 0) {
    $folders = [ordered]@{}
    $wf = Get-WatchFolders
    foreach ($k in $wf.Keys) {
      $folders[$k] = Get-FolderFileCount $wf[$k] -CacheSec 8
    }
    $script:QueuePaint.folders = $folders
    $script:QueuePaint.lastFolderScan = $now
  }
  Set-FolderBarRow $script:BarRows.folders $script:QueuePaint.folders

  # ---- MAIN board (ASCII bars + counts) ----
  $main = New-Object System.Text.StringBuilder
  [void]$main.AppendLine('══ FAFO DOCKWATCHER  ·  QUEUE BOARD ══')
  [void]$main.AppendLine($script:QueuePaint.exclusive)
  [void]$main.AppendLine('')
  [void]$main.Append((Format-QueueBlock 'VIDEO QUEUE' $v))
  [void]$main.Append((Format-QueueBlock 'IMAGE QUEUE' $i))
  [void]$main.Append((Format-QueueBlock 'TOOLBOX QUEUE' $tb))
  [void]$main.Append((Format-QueueBlock 'GROUP THERAPY' $g))
  [void]$main.AppendLine('FOLDER DEPTH  ( [n] = at least n files )')
  foreach ($name in @($script:QueuePaint.folders.Keys)) {
    $cnt = [int]$script:QueuePaint.folders[$name]
    [void]$main.AppendLine(('{0,-16} {1}' -f $name, (Format-TierLine $cnt)))
  }
  [void]$main.AppendLine('')
  $ms = [Environment]::TickCount - $t0
  [void]$main.AppendLine(('Updated {0:HH:mm:ss.fff}  ·  poll {1}ms  ·  refresh {2}ms' -f (Get-Date), $ms, $script:PollIntervalMs))
  $mainText = $main.ToString()
  if ($txtMain.Text -ne $mainText) {
    $txtMain.Text = $mainText
  }

  # ---- LIVE STATUS.txt (trim huge files for speed) ----
  $statusText = New-Object System.Text.StringBuilder
  foreach ($n in @('video', 'image', 'toolbox', 'group')) {
    $sp = Join-Path $FlashVsrApp "outputs\work_queue_$n\STATUS.txt"
    if (Test-Path $sp) {
      try {
        # first ~50 lines — enough for current RUN + next few WAIT
        $lines = Get-Content -LiteralPath $sp -TotalCount 50 -ErrorAction SilentlyContinue
        if ($lines) {
          [void]$statusText.AppendLine("===== $n =====")
          foreach ($ln in $lines) { [void]$statusText.AppendLine($ln) }
          $fi = Get-Item $sp
          if ($fi.Length -gt 5000) {
            [void]$statusText.AppendLine('... (truncated for speed — full file on disk)')
          }
          [void]$statusText.AppendLine()
        }
      } catch {}
    }
  }
  if ($statusText.Length -eq 0) {
    [void]$statusText.AppendLine('(no STATUS.txt yet — start a FlashVSR queue to see live progress here)')
  }
  $newText = $statusText.ToString()
  if ($txtLive.Text -ne $newText) {
    $txtLive.Text = $newText
  }

  # Status line shows active step at a glance
  $active = $null
  foreach ($s in @($g, $tb, $v, $i)) {
    if ($s -and $s.phase -eq 'running') { $active = $s; break }
  }
  if ($active) {
    Set-Status ("▶ {0}: {1}" -f $active.name.ToUpper(), $active.step_label) 'accent'
  }
}

function Cycle-App([int]$delta) {
  if ($script:Cycle.Count -eq 0) { return }
  $script:Dock.index = ($script:Dock.index + $delta) % $script:Cycle.Count
  if ($script:Dock.index -lt 0) { $script:Dock.index += $script:Cycle.Count }
  Save-Dock $script:Dock
  Refresh-AppLabel
  Set-Status ("Selected {0} (not opening anything)" -f (Current-App).label) 'accent'
  # Only open UI if user explicitly enabled auto-open
  if ($chkAutoOpen.Checked) {
    Open-CurrentAppUi
  }
}

function Open-CurrentAppUi {
  # Open Gradio/UI via pterm ONLY — never Explorer, never bare folder path
  $app = Current-App
  if (-not $app) { Set-Status 'No app selected' 'bad'; return }

  if (-not (Test-PinokioControlPlane).ok) {
    if (-not (Start-PinokioDesktop -WaitReady)) {
      Set-Status 'Pinokio offline — click Launch Pinokio first' 'bad'
      return
    }
  }

  # Prefer app id (name) over filesystem path so pterm does not treat path as a folder
  $target = if ($app.id) { $app.id } else { $app.label }
  Set-Status ("Opening UI for $target via pterm (no Explorer)...") 'accent'

  # status JSON may include ready_url
  $st = Invoke-Pterm @('status', $target) -TimeoutSec 12
  $readyUrl = $null
  if ($st.out) {
    if ($st.out -match '"ready_url"\s*:\s*"(http[^"]+)"') { $readyUrl = $Matches[1] }
    elseif ($st.out -match "'ready_url'\s*:\s*'(http[^']+)'") { $readyUrl = $Matches[1] }
  }

  if ($readyUrl) {
    # Open URL in Pinokio popup — NOT explorer
    $open = Invoke-Pterm @('open', $readyUrl, '--preset', 'center-large') -TimeoutSec 15
    if ($open.ok) {
      Set-Status ("Opened $readyUrl") 'ok'
      return
    }
  }

  # pterm open <app_id> — never pass raw filesystem path as sole arg if it looks like a folder
  $open2 = Invoke-Pterm @('open', $target, '--preset', 'center-large') -TimeoutSec 15
  if ($open2.ok) {
    Set-Status ("Opened $target") 'ok'
    return
  }

  # Last resort: pterm run only (starts script, does not open Explorer)
  $run = Invoke-Pterm @('run', $target) -TimeoutSec 8
  if ($run.ok -or $run.code -eq 0) {
    Set-Status ("Started $target (run). Use Open UI again when ready_url appears.") 'ok'
    return
  }

  Set-Status ("Could not open UI (pterm). Pinokio online? err=$($open2.err)$($open2.error)") 'bad'
  Write-DockLog ("open fail target=$target out=$($open2.out) err=$($open2.err)")
}

function Run-CurrentApp {
  $app = Current-App
  if (-not $app) { return }
  if (-not (Test-PinokioControlPlane).ok) {
    if (-not (Start-PinokioDesktop -WaitReady)) { return }
  }
  $target = if ($app.id) { $app.id } else { $app.label }
  Set-Status ("pterm run $target ...") 'accent'
  $r = Invoke-Pterm @('run', $target) -TimeoutSec 10
  if ($r.ok -or ($r.err -notmatch 'ECONNREFUSED')) {
    Set-Status ("Run requested for $target (app keeps running when you switch)") 'ok'
  } else {
    Set-Status ("Run failed: $($r.err)$($r.error)") 'bad'
  }
}

# buttons
$btnPinokio.Add_Click({
  $btnPinokio.Enabled = $false
  try { [void](Start-PinokioDesktop -WaitReady) } finally { $btnPinokio.Enabled = $true }
})
$btnPrev.Add_Click({ Cycle-App -1 })
$btnNext.Add_Click({ Cycle-App 1 })
$btnOpen.Add_Click({ Open-CurrentAppUi })
$btnRun.Add_Click({ Run-CurrentApp })
$btnRefresh.Add_Click({ Refresh-LiveData; Set-Status 'Data refreshed' 'ok' })
$btnSave.Add_Click({
  try {
    $path = Save-ProfileFromFlashVsr ("FlashVSR " + (Get-Date -Format 'yyyy-MM-dd HHmm'))
    Refresh-ProfileCombo
    Set-Status "Saved $path" 'ok'
  } catch { Set-Status $_.Exception.Message 'bad' }
})
$btnApply.Add_Click({
  try {
    $item = $cboProfile.SelectedItem
    if (-not $item) { Set-Status 'Pick a profile' 'bad'; return }
    $msg = Apply-Profile $item.Path
    Set-Status $msg 'ok'
  } catch { Set-Status $_.Exception.Message 'bad' }
})

$form.KeyPreview = $true
$form.Add_KeyDown({
  param($s, $e)
  if ($e.KeyCode -eq 'Left') { Cycle-App -1; $e.Handled = $true }
  elseif ($e.KeyCode -eq 'Right') { Cycle-App 1; $e.Handled = $true }
  elseif ($e.KeyCode -eq 'F5') { Refresh-LiveData; $e.Handled = $true }
})

# timer — data only, no Activate, no Explorer
# Fast poll (750ms) so step bars feel live; folder scan still throttled inside Refresh-LiveData
$script:PollIntervalMs = 750
$timer = New-Object Windows.Forms.Timer
$timer.Interval = $script:PollIntervalMs
$timer.Add_Tick({
  try { Refresh-LiveData } catch { Write-DockLog $_.Exception.Message }
})

# tray
$script:AllowClose = $false
try {
  $ni = New-Object Windows.Forms.NotifyIcon
  $ni.Text = 'FAFO Dockwatcher'
  $ni.Icon = [Drawing.SystemIcons]::Application
  $ni.Visible = $true
  $menu = New-Object Windows.Forms.ContextMenuStrip
  $miShow = $menu.Items.Add('Show FAFO Dockwatcher')
  $miShow.Add_Click({ $form.Show(); Enable-DarkTitleBar $form; if ($chkPin.Checked) { Set-PinNoActivate $form $true } })
  $miPk = $menu.Items.Add('Launch Pinokio')
  $miPk.Add_Click({ [void](Start-PinokioDesktop -WaitReady) })
  $miX = $menu.Items.Add('Exit')
  $miX.Add_Click({ $script:AllowClose = $true; $form.Close() })
  $ni.ContextMenuStrip = $menu
  $ni.Add_DoubleClick({ $form.Show(); Enable-DarkTitleBar $form })
  $form.Add_FormClosed({ $ni.Visible = $false; $ni.Dispose() })
} catch {}

$form.Add_FormClosing({
  param($s, $e)
  if (-not $script:AllowClose) { $e.Cancel = $true; $form.Hide() }
})
$form.Add_FormClosed({ $timer.Stop(); $timer.Dispose() })

$form.Add_Shown({
  Enable-DarkTitleBar $form
  if ($chkPin.Checked) { Set-PinNoActivate $form $true }
  Refresh-AppLabel
  Refresh-ProfileCombo
  Refresh-LiveData
  $timer.Start()
  $exe = Get-PinokioExe
  if ((Test-PinokioControlPlane).ok) { Set-Status ("FAFO Dockwatcher · online · queues every {0}ms" -f $script:PollIntervalMs) 'ok' }
  elseif (Test-PinokioProcess) { Set-Status 'Pinokio process up — waiting for API' 'accent' }
  elseif ($exe) { Set-Status "Offline — Launch Pinokio ($exe)" 'accent' }
  else { Set-Status 'Pinokio.exe not found' 'bad' }
})

if ($StartMinimized) { $form.WindowState = 'Minimized'; $form.Show(); $form.Hide() }
else { $form.Show() }

$ctx = New-Object Windows.Forms.ApplicationContext
$form.Add_FormClosed({ $ctx.ExitThread() })
[Windows.Forms.Application]::Run($ctx)
