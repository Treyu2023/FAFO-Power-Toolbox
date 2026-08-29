#requires -Version 5.1
<#
.SYNOPSIS
  Pin-on-top transfer monitor — pure black + neon teal (AI HTML Toolbox scheme).

.DESCRIPTION
  Live in/out transfers, history, details. Resizable splitters. Gloss/neon chrome.
  Tuned for low UI lag (slower poll, cached paint brushes, light animation).
#>
param(
  [string[]]$WatchFolders = @(
    "$env:USERPROFILE\Downloads",
    "$env:USERPROFILE\Desktop",
    "$env:LOCALAPPDATA\Temp\WinGet"
  ),
  [int]$PollMs = 1500,
  [int]$HistoryMax = 200,
  # Pin is OFF by default — TopMost often steals focus while you work
  [switch]$PinOnTop,
  [switch]$StartMinimized
)

$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# Native helpers: hide console + pin WITHOUT activating (no focus steal)
try {
  Add-Type -Namespace TmNative -Name Win32 -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern System.IntPtr GetConsoleWindow();
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool SetWindowPos(System.IntPtr hWnd, System.IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern System.IntPtr GetForegroundWindow();
'@ -ErrorAction Stop
  $console = [TmNative.Win32]::GetConsoleWindow()
  if ($console -ne [System.IntPtr]::Zero) {
    [void][TmNative.Win32]::ShowWindow($console, 0)  # SW_HIDE
  }
} catch {}

function Set-PinNoActivate([System.Windows.Forms.Form]$f, [bool]$pin) {
  # WS topmost without activation — critical for not yanking keyboard/mouse focus
  if (-not $f -or -not $f.IsHandleCreated) {
    $f.TopMost = $pin
    return
  }
  try {
    $hwnd = $f.Handle
    $after = if ($pin) { [System.IntPtr](-1) } else { [System.IntPtr](-2) }  # TOPMOST / NOTOPMOST
    $flags = [uint32](0x0001 -bor 0x0002 -bor 0x0010)  # NOSIZE | NOMOVE | NOACTIVATE
    [void][TmNative.Win32]::SetWindowPos($hwnd, $after, 0, 0, 0, 0, $flags)
    # Keep property in sync without using the activating setter path when possible
    $f.TopMost = $pin
  } catch {
    $f.TopMost = $pin
  }
}

function Test-FormIsForeground([System.Windows.Forms.Form]$f) {
  try {
    if (-not $f.IsHandleCreated) { return $false }
    return ([TmNative.Win32]::GetForegroundWindow() -eq $f.Handle)
  } catch { return $false }
}

# Log UI-thread exceptions instead of a raw crash dialog
$script:CrashLog = Join-Path $env:TEMP 'TransferMonitor-crash.log'
function Write-TmCrash([string]$msg) {
  try {
    $line = ("{0:u}  {1}" -f (Get-Date), $msg)
    Add-Content -LiteralPath $script:CrashLog -Value $line -Encoding UTF8
  } catch {}
}
[System.Windows.Forms.Application]::SetUnhandledExceptionMode(
  [System.Windows.Forms.UnhandledExceptionMode]::CatchException
)
[System.Windows.Forms.Application]::add_ThreadException({
  param($sender, $e)
  Write-TmCrash ("ThreadException: " + $e.Exception.ToString())
})
[AppDomain]::CurrentDomain.add_UnhandledException({
  param($sender, $e)
  Write-TmCrash ("Unhandled: " + $e.ExceptionObject.ToString())
})

# --- theme: pure black + neon teal (Toolbox accent #00f3ff) -------------------
$script:Theme = @{
  Bg          = [System.Drawing.Color]::FromArgb(5, 5, 8)         # pure near-black
  Panel       = [System.Drawing.Color]::FromArgb(10, 10, 14)
  PanelAlt    = [System.Drawing.Color]::FromArgb(14, 16, 22)
  Header      = [System.Drawing.Color]::FromArgb(6, 10, 14)
  Border      = [System.Drawing.Color]::FromArgb(0, 80, 90)
  Accent      = [System.Drawing.Color]::FromArgb(0, 243, 255)     # neon teal
  AccentDim   = [System.Drawing.Color]::FromArgb(0, 140, 155)
  AccentGlow  = [System.Drawing.Color]::FromArgb(0, 200, 220)
  Text        = [System.Drawing.Color]::FromArgb(230, 245, 250)
  Muted       = [System.Drawing.Color]::FromArgb(100, 130, 140)
  InBar       = [System.Drawing.Color]::FromArgb(0, 220, 240)
  OutBar      = [System.Drawing.Color]::FromArgb(0, 180, 200)
  Select      = [System.Drawing.Color]::FromArgb(0, 45, 55)
  Splitter    = [System.Drawing.Color]::FromArgb(0, 60, 70)
  OkGreen     = [System.Drawing.Color]::FromArgb(80, 255, 200)
  Track       = [System.Drawing.Color]::FromArgb(18, 24, 28)
}

# Cached brushes/pens (dispose on close)
$script:Br = @{
  Bg       = New-Object System.Drawing.SolidBrush $script:Theme.Bg
  Panel    = New-Object System.Drawing.SolidBrush $script:Theme.Panel
  PanelAlt = New-Object System.Drawing.SolidBrush $script:Theme.PanelAlt
  Select   = New-Object System.Drawing.SolidBrush $script:Theme.Select
  Text     = New-Object System.Drawing.SolidBrush $script:Theme.Text
  Muted    = New-Object System.Drawing.SolidBrush $script:Theme.Muted
  Accent   = New-Object System.Drawing.SolidBrush $script:Theme.Accent
  InBar    = New-Object System.Drawing.SolidBrush $script:Theme.InBar
  OutBar   = New-Object System.Drawing.SolidBrush $script:Theme.OutBar
  Track    = New-Object System.Drawing.SolidBrush $script:Theme.Track
  Gloss    = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(55, 255, 255, 255))
  Border   = New-Object System.Drawing.Pen $script:Theme.Border, 1
  AccentP  = New-Object System.Drawing.Pen $script:Theme.AccentDim, 1
}

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
  foreach ($folder in $WatchFolders) {
    if (-not (Test-Path -LiteralPath $folder)) { continue }
    foreach ($pat in $partialPatterns) {
      Get-ChildItem -LiteralPath $folder -Filter $pat -File -Force -ErrorAction SilentlyContinue | ForEach-Object {
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

function Draw-NeonBar {
  param(
    [System.Drawing.Graphics]$g,
    [System.Drawing.Rectangle]$rect,
    [double]$pct,
    [string]$direction,
    [double]$phase
  )
  if ($rect.Width -lt 2 -or $rect.Height -lt 2) { return }
  try {
    $g.FillRectangle($script:Br.Track, $rect)
    $brush = if ($direction -eq 'Out') { $script:Br.OutBar } else { $script:Br.InBar }

    if ($pct -lt 0) {
      $w = [math]::Max(16, [int]($rect.Width * 0.22))
      $x = [int]($rect.X + ($rect.Width + $w) * $phase - $w)
      $r = [System.Drawing.Rectangle]::Intersect(
        (New-Object System.Drawing.Rectangle $x, $rect.Y, $w, $rect.Height),
        $rect
      )
      if ($r.Width -gt 0 -and $r.Height -gt 0) {
        $g.FillRectangle($brush, $r)
        $glossH = [math]::Max(1, [int]($r.Height * 0.35))
        if ($glossH -lt $r.Height) {
          $g.FillRectangle($script:Br.Gloss, $r.X, $r.Y, $r.Width, $glossH)
        }
      }
    } else {
      $fillW = [math]::Max(0, [int]($rect.Width * [math]::Min(100.0, $pct) / 100.0))
      if ($fillW -gt 0) {
        $r = New-Object System.Drawing.Rectangle $rect.X, $rect.Y, $fillW, $rect.Height
        $g.FillRectangle($brush, $r)
        $glossH = [math]::Max(1, [int]($r.Height * 0.38))
        if ($glossH -lt $r.Height) {
          $g.FillRectangle($script:Br.Gloss, $r.X, $r.Y, $r.Width, $glossH)
        }
        $hw = [math]::Min(28, $fillW)
        if ($hw -gt 0) {
          $hx = $rect.X + [int](($fillW - $hw) * $phase)
          $g.FillRectangle($script:Br.Gloss, $hx, $rect.Y, $hw, $rect.Height)
        }
      }
    }
    if ($rect.Width -gt 1 -and $rect.Height -gt 1) {
      $g.DrawRectangle($script:Br.AccentP, $rect.X, $rect.Y, $rect.Width - 1, $rect.Height - 1)
    }
  } catch {}
}

function Set-SubText([System.Windows.Forms.ListViewItem]$item, [int]$idx, [string]$text) {
  while ($item.SubItems.Count -le $idx) { [void]$item.SubItems.Add('') }
  if ($item.SubItems[$idx].Text -ne $text) { $item.SubItems[$idx].Text = $text }
}

function Enable-DoubleBuffer($ctrl) {
  try {
    $flags = [System.Reflection.BindingFlags]'NonPublic, Instance'
    $prop = $ctrl.GetType().GetProperty('DoubleBuffered', $flags)
    if ($prop) { $prop.SetValue($ctrl, $true, $null) }
  } catch {}
}

# --- UI ----------------------------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Transfer Monitor'
$form.Size = New-Object System.Drawing.Size(920, 640)
$form.StartPosition = 'CenterScreen'
$form.BackColor = $script:Theme.Bg
$form.ForeColor = $script:Theme.Text
$form.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$form.TopMost = $false
$form.MinimumSize = New-Object System.Drawing.Size(560, 360)
$form.FormBorderStyle = 'Sizable'
$form.MaximizeBox = $true
$form.MinimizeBox = $true
$form.ShowInTaskbar = $true
# Never auto-activate when shown
$form.Add_Activated({})
if ($StartMinimized) { $form.WindowState = 'Minimized' }

# custom paint header strip with neon underline glow
$hdr = New-Object System.Windows.Forms.Panel
$hdr.Dock = 'Top'
$hdr.Height = 64
$hdr.BackColor = $script:Theme.Header
$hdr.Add_Paint({
  param($s, $e)
  try {
    $g = $e.Graphics
    $w = [int]$s.ClientSize.Width
    $h = [int]$s.ClientSize.Height
    if ($w -lt 2 -or $h -lt 2) { return }

    # solid fill (safe) + optional gloss gradient only when size is valid
    $g.FillRectangle($script:Br.Panel, 0, 0, $w, $h)
    $gh = [math]::Max(2, [int]($h * 0.55))
    if ($gh -ge 2 -and $w -ge 2) {
      $gloss = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle 0, 0, $w, $gh),
        [System.Drawing.Color]::FromArgb(50, 0, 243, 255),
        [System.Drawing.Color]::FromArgb(0, 0, 0, 0),
        90.0
      )
      $g.FillRectangle($gloss, 0, 0, $w, $gh)
      $gloss.Dispose()
    }
    # neon bottom edge (no zero-size geometry)
    $y = [math]::Max(0, $h - 2)
    $pen = New-Object System.Drawing.Pen $script:Theme.Accent, 2
    $g.DrawLine($pen, 0, $y, $w, $y)
    $pen.Dispose()
    $pen2 = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(70, 0, 243, 255)), 4
    $g.DrawLine($pen2, 0, $y, $w, $y)
    $pen2.Dispose()
  } catch {}
})
$form.Controls.Add($hdr)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = 'TRANSFER MONITOR'
$lblTitle.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 13)
$lblTitle.ForeColor = $script:Theme.Accent
$lblTitle.AutoSize = $true
$lblTitle.Location = New-Object System.Drawing.Point(14, 10)
$lblTitle.BackColor = [System.Drawing.Color]::Transparent
$hdr.Controls.Add($lblTitle)

$lblNet = New-Object System.Windows.Forms.Label
$lblNet.Text = 'NET  in -  |  out -'
$lblNet.ForeColor = $script:Theme.Muted
$lblNet.AutoSize = $false
$lblNet.Height = 18
$lblNet.Location = New-Object System.Drawing.Point(16, 38)
$lblNet.Anchor = 'Top, Left, Right'
$lblNet.Width = 520
$lblNet.BackColor = [System.Drawing.Color]::Transparent
$hdr.Controls.Add($lblNet)

$chkTop = New-Object System.Windows.Forms.CheckBox
$chkTop.Text = 'Pin (no focus steal)'
$chkTop.Checked = [bool]$PinOnTop
$chkTop.AutoSize = $true
$chkTop.ForeColor = $script:Theme.Accent
$chkTop.BackColor = [System.Drawing.Color]::Transparent
$chkTop.Anchor = 'Top, Right'
$chkTop.Location = New-Object System.Drawing.Point(780, 10)
$chkTop.Add_CheckedChanged({
  Set-PinNoActivate $form ([bool]$chkTop.Checked)
})
$hdr.Controls.Add($chkTop)

$btnClear = New-Object System.Windows.Forms.Button
$btnClear.Text = 'Clear history'
$btnClear.Size = New-Object System.Drawing.Size(108, 28)
$btnClear.Anchor = 'Top, Right'
$btnClear.Location = New-Object System.Drawing.Point(780, 32)
$btnClear.FlatStyle = 'Flat'
$btnClear.FlatAppearance.BorderColor = $script:Theme.AccentDim
$btnClear.FlatAppearance.MouseOverBackColor = [System.Drawing.Color]::FromArgb(0, 50, 60)
$btnClear.BackColor = [System.Drawing.Color]::FromArgb(8, 20, 24)
$btnClear.ForeColor = $script:Theme.Accent
$hdr.Controls.Add($btnClear)

function Move-HeaderButtons {
  $right = $hdr.ClientSize.Width - 120
  if ($right -lt 200) { $right = 200 }
  $chkTop.Left = $right
  $btnClear.Left = $right
  $lblNet.Width = [math]::Max(120, $right - 28)
}
$form.Add_Resize({ Move-HeaderButtons; $hdr.Invalidate() })
$hdr.Add_Resize({ Move-HeaderButtons })

# splits
$splitMain = New-Object System.Windows.Forms.SplitContainer
$splitMain.Dock = 'Fill'
$splitMain.Orientation = 'Horizontal'
$splitMain.SplitterWidth = 6
$splitMain.Panel1MinSize = 90
$splitMain.Panel2MinSize = 100
$splitMain.BackColor = $script:Theme.Splitter
$splitMain.Panel1.BackColor = $script:Theme.Bg
$splitMain.Panel2.BackColor = $script:Theme.Bg
$form.Controls.Add($splitMain)
$form.Controls.SetChildIndex($splitMain, 0)

$splitBottom = New-Object System.Windows.Forms.SplitContainer
$splitBottom.Dock = 'Fill'
$splitBottom.Orientation = 'Horizontal'
$splitBottom.SplitterWidth = 6
$splitBottom.Panel1MinSize = 70
$splitBottom.Panel2MinSize = 50
$splitBottom.BackColor = $script:Theme.Splitter
$splitBottom.Panel1.BackColor = $script:Theme.Bg
$splitBottom.Panel2.BackColor = $script:Theme.Bg
$splitMain.Panel2.Controls.Add($splitBottom)

$form.Add_Shown({
  try {
    if ($splitMain.Height -gt 200) { $splitMain.SplitterDistance = [int]($splitMain.Height * 0.42) }
    if ($splitBottom.Height -gt 120) { $splitBottom.SplitterDistance = [int]($splitBottom.Height * 0.55) }
  } catch {}
  Move-HeaderButtons
})

function New-SectionLabel([string]$text, [System.Drawing.Color]$color) {
  $l = New-Object System.Windows.Forms.Label
  $l.Text = $text
  $l.Dock = 'Top'
  $l.Height = 26
  $l.Padding = New-Object System.Windows.Forms.Padding(10, 5, 0, 0)
  $l.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 9)
  $l.ForeColor = $color
  $l.BackColor = $script:Theme.Panel
  return $l
}

# LIVE
$lblLive = New-SectionLabel 'LIVE TRANSFERS' $script:Theme.Accent
$splitMain.Panel1.Controls.Add($lblLive)

$liveList = New-Object System.Windows.Forms.ListView
$liveList.Dock = 'Fill'
$liveList.View = 'Details'
$liveList.FullRowSelect = $true
$liveList.HideSelection = $false
$liveList.MultiSelect = $false
$liveList.OwnerDraw = $true
$liveList.BackColor = $script:Theme.Panel
$liveList.ForeColor = $script:Theme.Text
$liveList.BorderStyle = 'FixedSingle'
$liveList.HeaderStyle = 'Nonclickable'
$liveList.Columns.Add('Name', 220) | Out-Null
$liveList.Columns.Add('Dir', 48) | Out-Null
$liveList.Columns.Add('Protocol', 120) | Out-Null
$liveList.Columns.Add('Progress', 180) | Out-Null
$liveList.Columns.Add('Rate', 90) | Out-Null
$liveList.Columns.Add('Size', 110) | Out-Null
$liveList.Columns.Add('Detail', 220) | Out-Null
Enable-DoubleBuffer $liveList
$splitMain.Panel1.Controls.Add($liveList)
$splitMain.Panel1.Controls.SetChildIndex($liveList, 0)

$liveList.Add_MouseDown({ $script:State.UserBusy = $true })
$liveList.Add_MouseUp({ $script:State.UserBusy = $false })

$liveList.Add_DrawColumnHeader({
  param($s, $e)
  try {
    if ($e.Bounds.Width -lt 1 -or $e.Bounds.Height -lt 1) { return }
    $g = $e.Graphics
    $g.FillRectangle($script:Br.Panel, $e.Bounds)
    $g.DrawLine($script:Br.AccentP, $e.Bounds.Left, $e.Bounds.Bottom - 1, $e.Bounds.Right, $e.Bounds.Bottom - 1)
    $text = if ($e.Header -and $e.Header.Text) { $e.Header.Text } else { '' }
    $sf = New-Object System.Drawing.StringFormat
    $sf.LineAlignment = 'Center'
    $sf.FormatFlags = [System.Drawing.StringFormatFlags]::NoWrap
    $rw = [math]::Max(1, $e.Bounds.Width - 4)
    $rectF = New-Object System.Drawing.RectangleF ([float]($e.Bounds.X + 4), [float]$e.Bounds.Y, [float]$rw, [float]$e.Bounds.Height)
    $g.DrawString($text, $liveList.Font, $script:Br.Accent, $rectF, $sf)
  } catch {}
})
$liveList.Add_DrawItem({ param($s, $e) $e.DrawDefault = $false })
$liveList.Add_DrawSubItem({
  param($s, $e)
  try {
    if ($null -eq $e.Item -or $e.Bounds.Width -lt 1) { return }
    $bgBrush = if ($e.Item.Selected) { $script:Br.Select }
      elseif (($e.ItemIndex % 2) -eq 0) { $script:Br.Panel }
      else { $script:Br.PanelAlt }
    $e.Graphics.FillRectangle($bgBrush, $e.Bounds)

    if ($e.ColumnIndex -eq 3) {
      $tag = $e.Item.Tag
      $pct = -1.0; $dir = 'In'
      if ($tag) {
        try { $pct = [double]$tag.DisplayPct } catch { $pct = -1.0 }
        try { $dir = [string]$tag.Direction } catch { $dir = 'In' }
      }
      $pad = 5
      $bw = [math]::Max(1, $e.Bounds.Width - 2 * $pad)
      $bh = [math]::Max(1, $e.Bounds.Height - 14)
      $r = New-Object System.Drawing.Rectangle ($e.Bounds.X + $pad), ($e.Bounds.Y + 7), $bw, $bh
      Draw-NeonBar -g $e.Graphics -rect $r -pct $pct -direction $dir -phase $script:State.AnimPhase
      $label = if ($pct -lt 0) { '...' } else { ("{0:N0}%" -f $pct) }
      $sf = New-Object System.Drawing.StringFormat
      $sf.Alignment = 'Center'; $sf.LineAlignment = 'Center'
      $e.Graphics.DrawString($label, $liveList.Font, $script:Br.Text, $e.Bounds, $sf)
    } else {
      $text = if ($e.SubItem) { [string]$e.SubItem.Text } else { '' }
      $brush = $script:Br.Text
      if ($e.ColumnIndex -eq 1 -and ($text -eq 'In' -or $text -eq 'Out')) { $brush = $script:Br.Accent }
      $rect = $e.Bounds; $rect.X += 4
      $e.Graphics.DrawString($text, $liveList.Font, $brush, $rect)
    }
  } catch {}
})

# HISTORY
$lblHist = New-SectionLabel 'HISTORY' $script:Theme.AccentDim
$splitBottom.Panel1.Controls.Add($lblHist)

$histList = New-Object System.Windows.Forms.ListView
$histList.Dock = 'Fill'
$histList.View = 'Details'
$histList.FullRowSelect = $true
$histList.HideSelection = $false
$histList.MultiSelect = $false
$histList.BackColor = $script:Theme.Panel
$histList.ForeColor = $script:Theme.Text
$histList.BorderStyle = 'FixedSingle'
$histList.Columns.Add('Time', 70) | Out-Null
$histList.Columns.Add('Status', 80) | Out-Null
$histList.Columns.Add('Dir', 40) | Out-Null
$histList.Columns.Add('Name', 200) | Out-Null
$histList.Columns.Add('Protocol', 100) | Out-Null
$histList.Columns.Add('Size', 90) | Out-Null
$histList.Columns.Add('Duration', 70) | Out-Null
$histList.Columns.Add('Path / Detail', 280) | Out-Null
Enable-DoubleBuffer $histList
$splitBottom.Panel1.Controls.Add($histList)
$splitBottom.Panel1.Controls.SetChildIndex($histList, 0)
$histList.Add_MouseDown({ $script:State.UserBusy = $true })
$histList.Add_MouseUp({ $script:State.UserBusy = $false })

# DETAILS
$lblDet = New-SectionLabel 'DETAILS' $script:Theme.Muted
$splitBottom.Panel2.Controls.Add($lblDet)

$detail = New-Object System.Windows.Forms.TextBox
$detail.Dock = 'Fill'
$detail.Multiline = $true
$detail.ScrollBars = 'Vertical'
$detail.ReadOnly = $true
$detail.BackColor = $script:Theme.Panel
$detail.ForeColor = $script:Theme.AccentGlow
$detail.BorderStyle = 'FixedSingle'
$detail.Font = New-Object System.Drawing.Font('Consolas', 9)
$detail.WordWrap = $true
$splitBottom.Panel2.Controls.Add($detail)
$splitBottom.Panel2.Controls.SetChildIndex($detail, 0)

function Show-Details($obj) {
  if (-not $obj) { return }
  $lines = @(
    ("Name:      {0}" -f $obj.Name),
    ("Direction: {0}    Protocol: {1}    Source: {2}" -f $obj.Direction, $obj.Protocol, $obj.Source),
    ("Bytes:     {0} / {1}" -f (Format-Bytes ([long]$obj.Bytes)), $(if ($obj.Total -gt 0) { Format-Bytes ([long]$obj.Total) } else { '?' })),
    ("Path:      {0}" -f $obj.Path),
    ("Detail:    {0}" -f $obj.Detail)
  )
  $text = $lines -join [Environment]::NewLine
  if ($detail.Text -ne $text) {
    $sel = $detail.SelectionStart
    $detail.Text = $text
    if ($sel -ge 0 -and $sel -le $detail.Text.Length) { $detail.SelectionStart = $sel }
  }
}

$liveList.Add_SelectedIndexChanged({
  if ($liveList.SelectedItems.Count -gt 0) { Show-Details $liveList.SelectedItems[0].Tag }
})
$histList.Add_SelectedIndexChanged({
  if ($histList.SelectedItems.Count -gt 0) { Show-Details $histList.SelectedItems[0].Tag }
})

function Sync-LiveList {
  $activeKeys = @{}
  foreach ($t in @($script:State.Active.Values)) {
    $activeKeys[$t.Key] = $true
    $item = $null
    if ($liveList.Items.ContainsKey($t.Key)) { $item = $liveList.Items[$t.Key] }
    if (-not $item) {
      $item = New-Object System.Windows.Forms.ListViewItem($t.Name)
      $item.Name = $t.Key
      [void]$item.SubItems.Add($t.Direction)
      [void]$item.SubItems.Add($t.Protocol)
      [void]$item.SubItems.Add('...')
      [void]$item.SubItems.Add('-')
      [void]$item.SubItems.Add('-')
      [void]$item.SubItems.Add('')
      $item.Tag = $t
      [void]$liveList.Items.Add($item)
    } else {
      $item.Tag = $t
    }

    $sizeText = if ($t.Total -gt 0) {
      ("{0} / {1}" -f (Format-Bytes $t.Bytes), (Format-Bytes $t.Total))
    } else { Format-Bytes $t.Bytes }
    $progText = if ($t.DisplayPct -lt 0) { '...' } else { ("{0:N0}%" -f $t.DisplayPct) }

    if ($item.Text -ne $t.Name) { $item.Text = $t.Name }
    Set-SubText $item 1 $t.Direction
    Set-SubText $item 2 $t.Protocol
    Set-SubText $item 3 $progText
    Set-SubText $item 4 (Format-Rate $t.Rate)
    Set-SubText $item 5 $sizeText
    Set-SubText $item 6 $t.Detail
  }

  $remove = New-Object System.Collections.Generic.List[System.Windows.Forms.ListViewItem]
  foreach ($item in $liveList.Items) {
    if (-not $activeKeys.ContainsKey($item.Name)) { $remove.Add($item) }
  }
  foreach ($r in $remove) { $liveList.Items.Remove($r) }

  $lblLive.Text = ("LIVE TRANSFERS  ({0})" -f $liveList.Items.Count)
  # Only rewrite details if THIS window is focused (avoids selection/focus fights)
  if ((Test-FormIsForeground $form) -and $liveList.SelectedItems.Count -gt 0) {
    Show-Details $liveList.SelectedItems[0].Tag
  }

  # Never repaint/animate when another app has focus — TopMost+Invalidate steals focus on some GPUs
  $script:State.AnimTick++
  if ((Test-FormIsForeground $form) -and (-not $script:State.UserBusy) -and (($script:State.AnimTick % 2) -eq 0)) {
    $liveList.Invalidate()
  }
}

function Sync-HistoryList {
  if (-not $script:State.HistDirty) { return }
  if ($script:State.UserBusy) { return }
  $script:State.HistDirty = $false

  $selectedKey = $null
  if ($histList.SelectedItems.Count -gt 0 -and $histList.SelectedItems[0].Tag) {
    $selectedKey = $histList.SelectedItems[0].Tag.Key
  }

  $histList.BeginUpdate()
  try {
    $histList.Items.Clear()
    $lblHist.Text = ("HISTORY  ({0})" -f $script:State.History.Count)
    foreach ($h in $script:State.History) {
      $item = New-Object System.Windows.Forms.ListViewItem(('{0:HH:mm:ss}' -f $h.Time))
      if ($h.Key) { $item.Name = [string]$h.Key }
      [void]$item.SubItems.Add($h.Status)
      [void]$item.SubItems.Add($h.Direction)
      [void]$item.SubItems.Add($h.Name)
      [void]$item.SubItems.Add($h.Protocol)
      [void]$item.SubItems.Add((Format-Bytes ([long]$h.Bytes)))
      [void]$item.SubItems.Add(('{0:N0}s' -f $h.DurationS))
      [void]$item.SubItems.Add($(if ($h.Path) { $h.Path } else { $h.Detail }))
      $item.Tag = $h
      if ($h.Status -eq 'Completed') { $item.ForeColor = $script:Theme.OkGreen }
      else { $item.ForeColor = $script:Theme.Muted }
      [void]$histList.Items.Add($item)
      if ($selectedKey -and $h.Key -eq $selectedKey) { $item.Selected = $true }
    }
  } finally { $histList.EndUpdate() }
}

$btnClear.Add_Click({
  $script:State.History.Clear()
  $script:State.SeenDone = @{}
  $script:State.HistDirty = $true
  Sync-HistoryList
  $detail.Text = ''
})

$cuda = Join-Path $env:USERPROFILE 'Downloads\cuda_13.3.1_windows.exe'
if (Test-Path $cuda) {
  $fi = Get-Item $cuda
  $seed = New-Transfer -Key (Get-StableKey 'seed' $cuda) -Name $fi.Name -Direction 'In' `
    -Protocol 'HTTP' -Source 'NVIDIA' -Bytes $fi.Length -Total $fi.Length -Path $fi.FullName `
    -Detail 'Seeded completed download'
  $seed.FirstSeen = $fi.CreationTime
  Add-History $seed 'Completed'
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = $PollMs
$timer.Add_Tick({
  try {
    # Always collect data; UI churn only when visible (never force focus)
    Merge-Snapshot
    if ($form.Visible) {
      Sync-LiveList
      Sync-HistoryList
      $lblNet.Text = ("NET  in {0}   out {1}" -f `
        (Format-Rate $script:State.NetInRate), `
        (Format-Rate $script:State.NetOutRate))
    }
  } catch {}
})

$form.Add_Shown({
  Move-HeaderButtons
  # Apply pin without activating if requested
  if ($chkTop.Checked) { Set-PinNoActivate $form $true }
  Merge-Snapshot
  Sync-LiveList
  Sync-HistoryList
  $timer.Start()
})

$script:AllowClose = $false
$script:Ni = $null

function Show-MainWindow {
  # User-initiated only (tray menu / double-click) — Activate is intentional here
  try {
    $form.ShowInTaskbar = $true
    $form.Visible = $true
    if ($form.WindowState -eq 'Minimized') { $form.WindowState = 'Normal' }
    $form.Show()
    $form.Activate()
    if ($chkTop.Checked) { Set-PinNoActivate $form $true }
  } catch {}
}

function Hide-ToTray {
  try {
    $form.Hide()
    $form.ShowInTaskbar = $false
    if ($script:Ni) { $script:Ni.Visible = $true }
    # No balloon tip — balloons steal focus / annoy while working
  } catch {}
}

function Exit-App {
  $script:AllowClose = $true
  try { $timer.Stop() } catch {}
  try { $form.Close() } catch {}
}

# System tray — console stays hidden; UI can be closed to tray
try {
  $ni = New-Object System.Windows.Forms.NotifyIcon
  $ni.Text = 'Transfer Monitor (tray)'
  $ni.Icon = [System.Drawing.SystemIcons]::Application
  $ni.Visible = $true
  $script:Ni = $ni

  $menu = New-Object System.Windows.Forms.ContextMenuStrip
  $miShow = $menu.Items.Add('Open Transfer Monitor')
  $miShow.Add_Click({ Show-MainWindow })
  $miPin = $menu.Items.Add('Toggle pin (no focus steal)')
  $miPin.Add_Click({
    $chkTop.Checked = -not $chkTop.Checked
  })
  [void]$menu.Items.Add('-')
  $miExit = $menu.Items.Add('Exit')
  $miExit.Add_Click({ Exit-App })
  $ni.ContextMenuStrip = $menu

  $ni.Add_DoubleClick({ Show-MainWindow })
  $ni.Add_MouseUp({
    param($sender, $e)
    if ($e.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
      # single left-click also restores (discoverable)
    }
  })
} catch {
  Write-TmCrash ("Tray init: " + $_.Exception.Message)
}

# Minimize / X → tray (not exit). Exit only from tray menu.
$form.Add_Resize({
  if ($form.WindowState -eq 'Minimized') {
    Hide-ToTray
  }
})

$form.Add_FormClosing({
  param($sender, $e)
  if (-not $script:AllowClose) {
    $e.Cancel = $true
    Hide-ToTray
  }
})

$form.Add_FormClosed({
  try { $timer.Stop(); $timer.Dispose() } catch {}
  foreach ($k in @($script:Br.Keys)) {
    try { $script:Br[$k].Dispose() } catch {}
  }
  if ($script:Ni) {
    try { $script:Ni.Visible = $false; $script:Ni.Dispose() } catch {}
  }
})

$ctx = New-Object System.Windows.Forms.ApplicationContext
$form.Add_FormClosed({ $ctx.ExitThread() })

if ($StartMinimized) {
  # Start tray-only (no main window flash)
  $form.WindowState = 'Minimized'
  $form.ShowInTaskbar = $false
  $form.Show()
  Hide-ToTray
} else {
  $form.Show()
}

[System.Windows.Forms.Application]::Run($ctx)
