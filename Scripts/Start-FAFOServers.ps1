# Start-FAFOServers.ps1
# Start configured companion servers only (no Chrome UI).
# Used by one-click launch and optional Windows Startup.
#
#   S1 HTML Toolbox Server       → 127.0.0.87:18765  (media, Verifone, system tools)
#   S2 FAFO Local Media Tagger   → 127.0.0.1:8765    (Chrome extension tags/ratings)

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [switch]$NoToolbox,
    [switch]$NoFafoMeta,
    [switch]$Force,
    [int]$HealthTimeoutSec = 20,
    [switch]$Quiet,
    [switch]$NoTray,
    [switch]$TrayOnly,
    [switch]$Restart
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}
$ToolboxRoot = (Resolve-Path -LiteralPath $ToolboxRoot).Path
$env:FAFO_TOOLBOX_ROOT = $ToolboxRoot

function Write-Srv([string]$Message, [string]$Color = 'Cyan') {
    if (-not $Quiet) { Write-Host $Message -ForegroundColor $Color }
}

function Get-LaunchPrefs {
    $path = Join-Path $env:LOCALAPPDATA 'FAFO\launch-prefs.json'
    $defaults = [ordered]@{
        startWithOneClick = [ordered]@{ toolboxServer = $true; fafoMetaServer = $true }
        serversSleeping   = [ordered]@{ toolboxServer = $false; fafoMetaServer = $false }
        sessions          = [ordered]@{ toolboxActive = $false }
        fafoMetaRoot      = $null
    }
    if (-not (Test-Path -LiteralPath $path)) { return [pscustomobject]$defaults }
    try {
        $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        $tb = $true; $meta = $true
        $sleepTb = $false; $sleepMeta = $false
        $sessTb = $false
        if ($raw.startWithOneClick) {
            if ($null -ne $raw.startWithOneClick.toolboxServer) { $tb = [bool]$raw.startWithOneClick.toolboxServer }
            if ($null -ne $raw.startWithOneClick.fafoMetaServer) { $meta = [bool]$raw.startWithOneClick.fafoMetaServer }
        }
        if ($raw.serversSleeping) {
            if ($null -ne $raw.serversSleeping.toolboxServer) { $sleepTb = [bool]$raw.serversSleeping.toolboxServer }
            if ($null -ne $raw.serversSleeping.fafoMetaServer) { $sleepMeta = [bool]$raw.serversSleeping.fafoMetaServer }
        }
        if ($raw.sessions -and $null -ne $raw.sessions.toolboxActive) {
            $sessTb = [bool]$raw.sessions.toolboxActive
        }
        return [pscustomobject]@{
            startWithOneClick = [pscustomobject]@{ toolboxServer = $tb; fafoMetaServer = $meta }
            serversSleeping   = [pscustomobject]@{ toolboxServer = $sleepTb; fafoMetaServer = $sleepMeta }
            sessions          = [pscustomobject]@{ toolboxActive = $sessTb }
            fafoMetaRoot      = $(if ($raw.fafoMetaRoot) { [string]$raw.fafoMetaRoot } else { $null })
        }
    } catch {
        return [pscustomobject]$defaults
    }
}

function Test-HttpOk([string]$Url, [int]$TimeoutSec = 2) {
    try {
        $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec -ErrorAction Stop
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300)
    } catch {
        return $false
    }
}

function Test-PortOpen([string]$HostName, [int]$Port, [int]$TimeoutMs = 400) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) { $client.Close(); return $false }
        $client.EndConnect($iar) | Out-Null
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Resolve-FafoMetaRoot([string]$Preferred) {
    $candidates = New-Object System.Collections.Generic.List[string]
    if ($Preferred) { [void]$candidates.Add($Preferred) }
    if ($env:FAFO_META_ROOT) { [void]$candidates.Add($env:FAFO_META_ROOT) }
    $lp = Join-Path $env:LOCALAPPDATA 'FAFO\local-paths.json'
    if (Test-Path -LiteralPath $lp) {
        try {
            $cfg = Get-Content -LiteralPath $lp -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach ($k in @('ExplorerMetaRoot', 'FafoMetaRoot', 'fafoMetaRoot')) {
                if ($cfg.$k) { [void]$candidates.Add([string]$cfg.$k) }
            }
        } catch {}
    }
    @(
        'C:\_Git\repos\html\fafo-chrome-extensions\FAFO Local Media LOAD THIS\explorer-meta'
        (Join-Path (Split-Path (Split-Path $ToolboxRoot -Parent) -Parent) 'fafo-chrome-extensions\FAFO Local Media LOAD THIS\explorer-meta')
        (Join-Path (Split-Path $ToolboxRoot -Parent) 'fafo-chrome-extensions\FAFO Local Media LOAD THIS\explorer-meta')
        'D:\Chrome python_HTML AI apps\FAFO Local Media LOAD THIS\explorer-meta'
        'D:\Chrome python_HTML AI apps\FAFO Local Media\explorer-meta'
        'D:\Chrome python_HTML AI apps\FAFO Ultimate Tab\explorer-meta'
        (Join-Path $env:USERPROFILE 'Documents\FAFO Ultimate Tab\explorer-meta')
        (Join-Path $env:USERPROFILE 'Desktop\FAFO Ultimate Tab\explorer-meta')
        (Join-Path (Split-Path $ToolboxRoot -Parent) 'FAFO Ultimate Tab\explorer-meta')
        (Join-Path $ToolboxRoot 'explorer-meta')
    ) | ForEach-Object { if ($_) { [void]$candidates.Add($_) } }

    foreach ($c in $candidates) {
        if (-not $c) { continue }
        $serverPy = Join-Path $c 'server.py'
        $bat = Join-Path $c 'START_META_SERVER.bat'
        if ((Test-Path -LiteralPath $serverPy) -or (Test-Path -LiteralPath $bat)) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }
    return $null
}

function Save-MetaRootHint([string]$Path) {
    if (-not $Path) { return }
    $prefsPath = Join-Path $env:LOCALAPPDATA 'FAFO\launch-prefs.json'
    $dir = Split-Path -Parent $prefsPath
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $obj = @{
        version           = 1
        startWithOneClick = @{ toolboxServer = $true; fafoMetaServer = $true }
        windowsStartup    = @{ servers = $false; app = $false }
        blockAutoStart    = @{ toolboxServer = $false; fafoMetaServer = $false }
        serversSleeping   = @{ toolboxServer = $false; fafoMetaServer = $false }
        fafoMetaRoot      = $Path
        updatedAt         = (Get-Date).ToString('o')
    }
    if (Test-Path -LiteralPath $prefsPath) {
        try {
            $existing = Get-Content -LiteralPath $prefsPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($existing.startWithOneClick) { $obj.startWithOneClick = $existing.startWithOneClick }
            if ($existing.windowsStartup) { $obj.windowsStartup = $existing.windowsStartup }
            if ($existing.blockAutoStart) { $obj.blockAutoStart = $existing.blockAutoStart }
            if ($existing.serversSleeping) { $obj.serversSleeping = $existing.serversSleeping }
            if ($existing.sessions) { $obj.sessions = $existing.sessions }
            $obj.fafoMetaRoot = $Path
            if ($existing.version) { $obj.version = $existing.version }
        } catch {}
    }
    ($obj | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $prefsPath -Encoding UTF8
    $lpPath = Join-Path $env:LOCALAPPDATA 'FAFO\local-paths.json'
    try {
        $lp = @{}
        if (Test-Path -LiteralPath $lpPath) {
            $raw = Get-Content -LiteralPath $lpPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $raw.PSObject.Properties | ForEach-Object { $lp[$_.Name] = $_.Value }
        }
        $lp['ExplorerMetaRoot'] = $Path
        $lp['UpdatedAt'] = (Get-Date).ToString('o')
        $lp['Machine'] = $env:COMPUTERNAME
        ($lp | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $lpPath -Encoding UTF8
    } catch {}
}

function Test-PythonExe([string]$Exe) {
    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe)) { return $false }
    try {
        # Avoid Start-Process -ArgumentList path-splitting bugs; use ProcessStartInfo
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $Exe
        $psi.Arguments = '-c "import sys"'
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardError = $true
        $psi.RedirectStandardOutput = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        if (-not $p.WaitForExit(8000)) {
            try { $p.Kill() } catch {}
            return $false
        }
        return ($p.ExitCode -eq 0)
    } catch {
        return $false
    }
}

function Get-ToolboxPython {
    # Prefer local .venv, then known production tree, then Resolve-FAFOPython / system.
    $candidates = New-Object System.Collections.Generic.List[string]
    [void]$candidates.Add((Join-Path $ToolboxRoot '.venv\Scripts\python.exe'))
    # Canonical production install (Desktop copy often lacks .venv after OneDrive/sync)
    [void]$candidates.Add('C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\python.exe')
    [void]$candidates.Add((Join-Path (Split-Path $ToolboxRoot -Parent) 'HTML Toolbox AI tools\production\.venv\Scripts\python.exe'))
    [void]$candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'))
    [void]$candidates.Add((Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'))
    foreach ($py in $candidates) {
        if (-not (Test-Path -LiteralPath $py)) { continue }
        # Prefer first existing path; soft-test but don't discard solely on flaky probe
        if (Test-PythonExe $py) {
            return (Resolve-Path -LiteralPath $py).Path
        }
        # Fallback: path exists and is python.exe — try anyway (probe can false-negative)
        if ($py -match 'python\.exe$') {
            Write-Srv " [i] Using python without probe OK: $py" 'DarkGray'
            return (Resolve-Path -LiteralPath $py).Path
        }
    }
    $resolver = Join-Path $PSScriptRoot 'Resolve-FAFOPython.ps1'
    if (Test-Path -LiteralPath $resolver) {
        try {
            $resolved = & $resolver -ToolboxRoot $ToolboxRoot 2>$null
            if ($resolved -and (Test-Path -LiteralPath ([string]$resolved))) {
                return [string]$resolved
            }
        } catch {}
    }
    return $null
}

function Get-ToolboxPythonw {
    # Tray / GUI helpers: pythonw is fine.
    $w = Join-Path $ToolboxRoot '.venv\Scripts\pythonw.exe'
    if (Test-Path -LiteralPath $w) { return (Resolve-Path -LiteralPath $w).Path }
    $py = Get-ToolboxPython
    if (-not $py) { return $null }
    $sibling = Join-Path (Split-Path $py -Parent) 'pythonw.exe'
    if (Test-Path -LiteralPath $sibling) { return (Resolve-Path -LiteralPath $sibling).Path }
    return $py
}

function Get-ServerPython {
    # Servers: python.exe + CreateNoWindow is more reliable than pythonw on some paths.
    return (Get-ToolboxPython)
}

function Ensure-LoopbackHost([string]$HostAddr) {
    # S1 binds 127.0.0.87 — Windows only has 127.0.0.1 by default.
    if (-not $HostAddr -or $HostAddr -eq '127.0.0.1' -or $HostAddr -eq '0.0.0.0' -or $HostAddr -eq '::1') {
        return $true
    }
    if ($HostAddr -notmatch '^127\.') { return $true }
    try {
        $hit = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -eq $HostAddr }
        if ($hit) { return $true }
    } catch {}
    $alias = 'Loopback Pseudo-Interface 1'
    try {
        New-NetIPAddress -IPAddress $HostAddr -PrefixLength 8 -InterfaceAlias $alias -ErrorAction Stop | Out-Null
        Write-Srv " [OK] Added loopback alias $HostAddr (needed for S1 bind)" 'Green'
        return $true
    } catch {
        try {
            $out = netsh interface ipv4 add address name="$alias" addr=$HostAddr mask=255.0.0.0 2>&1
            if ($LASTEXITCODE -eq 0 -or "$out" -match 'already|exists|Ok') {
                Write-Srv " [OK] Loopback alias $HostAddr via netsh" 'Green'
                return $true
            }
        } catch {}
        Write-Srv " [!] Could not add $HostAddr to loopback — S1 may fail to bind. Run elevated once or re-run setup." 'Yellow'
        return $false
    }
}

function Start-HiddenProcess {
    <#
    .SYNOPSIS
      Launch a process with no visible window (normal app behavior).
      Uses ProcessStartInfo — Start-Process -ArgumentList breaks on paths with spaces here.
    #>
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = $ToolboxRoot
    )
    if (-not (Test-Path -LiteralPath $FilePath)) {
        throw "Executable not found: $FilePath"
    }
    $parts = @()
    foreach ($a in @($ArgumentList)) {
        $s = [string]$a
        if ([string]::IsNullOrEmpty($s)) { continue }
        # Windows ProcessStartInfo: quote args that contain spaces
        if ($s -match '\s') {
            $parts += ('"' + ($s.Replace('"', '""')) + '"')
        } else {
            $parts += $s
        }
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = ($parts -join ' ')
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    # Prevent Windows cp1252 UnicodeEncodeError on S1 banner prints when redirected
    try {
        if (-not $psi.EnvironmentVariables.ContainsKey('PYTHONIOENCODING')) {
            $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
        }
        if (-not $psi.EnvironmentVariables.ContainsKey('PYTHONUTF8')) {
            $psi.EnvironmentVariables['PYTHONUTF8'] = '1'
        }
    } catch {}
    $p = [System.Diagnostics.Process]::Start($psi)
    if (-not $p) {
        throw "Failed to start process: $FilePath"
    }
    Start-Sleep -Milliseconds 400
    if ($p.HasExited) {
        throw "Process exited immediately (code $($p.ExitCode)): $FilePath $($psi.Arguments)"
    }
    return $p
}

function Test-TrayRunning {
    try {
        $procs = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe' OR Name = 'python.exe'" -ErrorAction SilentlyContinue
        foreach ($p in @($procs)) {
            $cmd = [string]$p.CommandLine
            if ($cmd -and $cmd -match 'tray_launcher\.py') { return $true }
        }
    } catch {}
    return $false
}

function Start-FafoTray {
    if ($NoTray) { return }
    if (Test-TrayRunning) {
        Write-Srv " [OK] Tray already running" 'DarkGray'
        return
    }
    $pyw = Get-ToolboxPythonw
    $tray = Join-Path $ToolboxRoot 'server\tray_launcher.py'
    if (-not $pyw -or -not (Test-Path -LiteralPath $tray)) {
        Write-Srv " [i] Tray skip (pythonw/tray_launcher missing)" 'DarkGray'
        return
    }
    try {
        $null = Start-HiddenProcess -FilePath $pyw -ArgumentList @($tray) -WorkingDirectory (Join-Path $ToolboxRoot 'server')
        Write-Srv " [OK] System tray helper started (auto-keeps servers running)" 'Green'
    } catch {
        Write-Srv " [i] Tray not started: $($_.Exception.Message)" 'DarkGray'
    }
}

# --- bind for toolbox health ---
$tbHost = '127.0.0.87'
$tbPort = 18765
$bindFile = Join-Path $ToolboxRoot 'shared\aitoolbox-bind.json'
if (Test-Path -LiteralPath $bindFile) {
    try {
        $bind = Get-Content -LiteralPath $bindFile -Raw | ConvertFrom-Json
        if ($bind.host) { $tbHost = [string]$bind.host }
        if ($bind.port) { $tbPort = [int]$bind.port }
    } catch {}
}
$tbHealth = "http://${tbHost}:${tbPort}/api/health"
$metaHealth = 'http://127.0.0.1:8765/api/health'

if ($TrayOnly) {
    Write-Srv " FAFO tray only" 'Cyan'
    Start-FafoTray
    exit 0
}

function Stop-ListenerOnPort([int]$Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in @($conns)) {
            $procId = $c.OwningProcess
            if ($procId -and $procId -gt 0) {
                Write-Srv " Stopping PID $procId on port $Port..." 'DarkGray'
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

$prefs = Get-LaunchPrefs
# Lifecycle (independent products):
#   S1 → with HTML Toolbox session (open Toolbox / -Force S1)
#   S2 → with Google Chrome process
# Sleep is sticky unless -Force / -Restart
$sleepTb = $false; $sleepMeta = $false
if ($prefs.serversSleeping) {
    $sleepTb = [bool]$prefs.serversSleeping.toolboxServer
    $sleepMeta = [bool]$prefs.serversSleeping.fafoMetaServer
}
$sessionTb = $false
if ($prefs.sessions) { $sessionTb = [bool]$prefs.sessions.toolboxActive }
$chromeUp = $false
try {
    $chromeUp = [bool](Get-Process -Name 'chrome' -ErrorAction SilentlyContinue | Select-Object -First 1)
} catch { $chromeUp = $false }

# Simple rules:
#   AUTO  (no -Force/-Restart): S1 if Toolbox session · S2 if Chrome
#   MANUAL (-Force or -Restart, or dedicated S1/S2 bats): start that server NOW
$manualStart = $Force -or $Restart
$wantToolbox = (-not $NoToolbox) -and (
    $manualStart -or (
        $prefs.startWithOneClick.toolboxServer -and -not $sleepTb -and $sessionTb
    )
)
# Manual always starts S2 if not -NoFafoMeta (Chrome not required)
$wantMeta = (-not $NoFafoMeta) -and (
    $manualStart -or (
        $prefs.startWithOneClick.fafoMetaServer -and -not $sleepMeta -and $chromeUp
    )
)

Write-Srv ""
Write-Srv " FAFO servers (S1=Toolbox · S2=Chrome auto / manual anytime)" 'Cyan'
Write-Srv "   S1 = HTML Toolbox Server (Toolbox apps only)" 'DarkGray'
Write-Srv "   S2 = Ultimate Tab / Local Media (Chrome auto; Start All forces S2)" 'DarkGray'
Write-Srv " Root: $ToolboxRoot"
Write-Srv "   Chrome running: $chromeUp · Toolbox session: $sessionTb · Manual: $manualStart" 'DarkGray'
if ($sleepTb -and -not $manualStart) {
    Write-Srv "   S1 is SLEEPING — skipped (tray: S1 → Start / wake)" 'Yellow'
}
if (-not $sessionTb -and -not $manualStart -and -not $NoToolbox) {
    Write-Srv "   S1 skipped — open HTML Toolbox to start S1" 'DarkGray'
}
if ($sleepMeta -and -not $manualStart) {
    Write-Srv "   S2 is SLEEPING — skipped (tray: S2 → Start / wake)" 'Yellow'
}
if (-not $chromeUp -and -not $NoFafoMeta -and -not $manualStart) {
    Write-Srv "   S2 skipped — Chrome not running (auto mode). Use Start All / -Force for S2 anytime." 'DarkGray'
}
if ($wantMeta -and -not $chromeUp -and $manualStart) {
    Write-Srv "   S2 manual start (Chrome not required)" 'Yellow'
}

if ($Restart) {
    Write-Srv " Restart requested — stopping listeners first..." 'Yellow'
    if ($wantToolbox) { Stop-ListenerOnPort $tbPort }
    if ($wantMeta) { Stop-ListenerOnPort 8765 }
    Start-Sleep -Milliseconds 700
}

$started = @()
$pyServer = Get-ServerPython
if (-not $pyServer -and ($wantToolbox -or $wantMeta)) {
    throw "Missing Python venv — run INSTALL-PYTHON.bat first (or keep production .venv at C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv)"
}
if ($pyServer) {
    Write-Srv " Python: $pyServer" 'DarkGray'
}

# S1 needs 127.0.0.87 assigned on loopback (not present on a stock Windows install)
if ($wantToolbox) {
    $null = Ensure-LoopbackHost $tbHost
}

# --- S1 HTML Toolbox Server ---
if ($wantToolbox) {
    if (Test-HttpOk $tbHealth) {
        Write-Srv " [OK] S1 HTML Toolbox already online @ ${tbHost}:${tbPort}" 'Green'
        $started += [pscustomobject]@{ id = 'toolbox'; ok = $true; already = $true }
    } else {
        Write-Srv " Starting S1 HTML Toolbox Server (hidden)..." 'Yellow'
        $serverPy = Join-Path $ToolboxRoot 'server\aitoolbox_server.py'
        if (-not (Test-Path -LiteralPath $serverPy)) {
            # Fall back to canonical production tree
            $alt = 'C:\_Git\repos\html\HTML Toolbox AI tools\production\server\aitoolbox_server.py'
            if (Test-Path -LiteralPath $alt) {
                $serverPy = $alt
                Write-Srv "     using production server.py" 'DarkGray'
            } else {
                throw "Missing $serverPy"
            }
        }
        try {
            $workDir = Split-Path -Parent $serverPy
            $null = Start-HiddenProcess -FilePath $pyServer -ArgumentList @($serverPy) -WorkingDirectory $workDir
            $started += [pscustomobject]@{ id = 'toolbox'; ok = $true; started = $true; hidden = $true }
        } catch {
            Write-Srv " [!] S1 HTML Toolbox start failed: $($_.Exception.Message)" 'Red'
            $started += [pscustomobject]@{ id = 'toolbox'; ok = $false; error = $_.Exception.Message }
        }
    }
} else {
    Write-Srv " [SKIP] S1 HTML Toolbox (open Toolbox app, or use -Force / 1-Start-HTML-Toolbox-Server.bat)" 'DarkGray'
}

# Mark S1 session + clear sleep/hold when we intentionally started servers
if (($wantToolbox -or $wantMeta) -and $pyServer) {
    try {
        $mark = @'
import sys
from pathlib import Path
root = Path(r"""TOOLBOX_ROOT""")
sys.path.insert(0, str(root / "server"))
import launch_ops
want_tb = WANT_TB
want_meta = WANT_META
if want_tb:
    launch_ops.set_toolbox_session(True)
    launch_ops.set_servers_sleeping(toolbox=False)
    launch_ops.set_manual_hold(toolbox=True)
if want_meta:
    launch_ops.set_servers_sleeping(fafo_meta=False)
    launch_ops.set_manual_hold(fafo_meta=True)
print("session/hold updated")
'@
        $mark = $mark.Replace('TOOLBOX_ROOT', $ToolboxRoot.Replace('\', '\\'))
        $mark = $mark.Replace('WANT_TB', $(if ($wantToolbox) { 'True' } else { 'False' }))
        $mark = $mark.Replace('WANT_META', $(if ($wantMeta) { 'True' } else { 'False' }))
        $tmp = Join-Path $env:TEMP 'fafo-mark-toolbox-session.py'
        Set-Content -LiteralPath $tmp -Value $mark -Encoding UTF8
        & $pyServer $tmp 2>$null | Out-Null
    } catch {}
}

# --- S2 Ultimate Tab / Local Media (Chrome lifecycle) ---
if ($wantMeta) {
    if (Test-HttpOk $metaHealth) {
        Write-Srv " [OK] S2 Ultimate Tab tagger already online @ 127.0.0.1:8765" 'Green'
        $started += [pscustomobject]@{ id = 'fafo_meta'; ok = $true; already = $true }
    } else {
        $metaRoot = Resolve-FafoMetaRoot -Preferred $prefs.fafoMetaRoot
        if (-not $metaRoot) {
            Write-Srv " [!] S2 FAFO Tagger path not found (explorer-meta)." 'Yellow'
            Write-Srv "     Expected: ...\fafo-chrome-extensions\FAFO Local Media LOAD THIS\explorer-meta" 'DarkGray'
            $started += [pscustomobject]@{ id = 'fafo_meta'; ok = $false; error = 'path not found' }
        } else {
            Save-MetaRootHint $metaRoot
            Write-Srv " Starting S2 FAFO Local Media Tagger (hidden)..." 'Yellow'
            Write-Srv "     $metaRoot" 'DarkGray'
            $serverPy = Join-Path $metaRoot 'server.py'
            if (Test-Path -LiteralPath $serverPy) {
                try {
                    $null = Start-HiddenProcess -FilePath $pyServer -ArgumentList @($serverPy) -WorkingDirectory $metaRoot
                    $started += [pscustomobject]@{ id = 'fafo_meta'; ok = $true; started = $true; path = $metaRoot; hidden = $true }
                } catch {
                    Write-Srv " [!] S2 FAFO Tagger start failed: $($_.Exception.Message)" 'Yellow'
                    $started += [pscustomobject]@{ id = 'fafo_meta'; ok = $false; error = $_.Exception.Message }
                }
            } else {
                Write-Srv " [!] No server.py in meta root" 'Red'
                $started += [pscustomobject]@{ id = 'fafo_meta'; ok = $false; error = 'no entrypoint' }
            }
        }
    }
} else {
    Write-Srv " [SKIP] S2 FAFO Local Media Tagger (disabled in launch prefs)" 'DarkGray'
}

# --- Wait for health ---
$deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
while ((Get-Date) -lt $deadline) {
    $tbOk = (-not $wantToolbox) -or (Test-HttpOk $tbHealth) -or (Test-PortOpen $tbHost $tbPort)
    $metaOk = (-not $wantMeta) -or (Test-HttpOk $metaHealth) -or (Test-PortOpen '127.0.0.1' 8765)
    if ($tbOk -and $metaOk) { break }
    Start-Sleep -Milliseconds 600
}

$finalTb = Test-HttpOk $tbHealth
$finalMeta = Test-HttpOk $metaHealth
if ($wantToolbox) {
    if ($finalTb) { Write-Srv " [OK] S1 HTML Toolbox @ ${tbHost}:${tbPort}" 'Green' }
    else { Write-Srv " [!] S1 HTML Toolbox not healthy yet — Desktop 'Start Servers' or tray Restart" 'Yellow' }
}
if ($wantMeta) {
    if ($finalMeta) { Write-Srv " [OK] S2 FAFO Local Media Tagger @ 127.0.0.1:8765" 'Green' }
    else { Write-Srv " [!] S2 FAFO Tagger not healthy yet (optional if you only use HTML tools)" 'Yellow' }
}

# System tray for relaunch without browsing install folders
Start-FafoTray

Write-Srv ""
exit 0
