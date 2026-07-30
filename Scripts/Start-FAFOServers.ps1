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
        fafoMetaRoot      = $null
    }
    if (-not (Test-Path -LiteralPath $path)) { return [pscustomobject]$defaults }
    try {
        $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        $tb = $true; $meta = $true
        if ($raw.startWithOneClick) {
            if ($null -ne $raw.startWithOneClick.toolboxServer) { $tb = [bool]$raw.startWithOneClick.toolboxServer }
            if ($null -ne $raw.startWithOneClick.fafoMetaServer) { $meta = [bool]$raw.startWithOneClick.fafoMetaServer }
        }
        return [pscustomobject]@{
            startWithOneClick = [pscustomobject]@{ toolboxServer = $tb; fafoMetaServer = $meta }
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
        fafoMetaRoot      = $Path
        updatedAt         = (Get-Date).ToString('o')
    }
    if (Test-Path -LiteralPath $prefsPath) {
        try {
            $existing = Get-Content -LiteralPath $prefsPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($existing.startWithOneClick) { $obj.startWithOneClick = $existing.startWithOneClick }
            if ($existing.windowsStartup) { $obj.windowsStartup = $existing.windowsStartup }
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

function Get-ToolboxPython {
    $py = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $py) { return $py }
    return $null
}

function Get-ToolboxPythonw {
    # Tray / GUI helpers: pythonw is fine.
    $w = Join-Path $ToolboxRoot '.venv\Scripts\pythonw.exe'
    if (Test-Path -LiteralPath $w) { return $w }
    return (Get-ToolboxPython)
}

function Get-ServerPython {
    # Servers: python.exe + CreateNoWindow is more reliable than pythonw on some paths.
    return (Get-ToolboxPython)
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
$wantToolbox = (-not $NoToolbox) -and ($Force -or $Restart -or $prefs.startWithOneClick.toolboxServer)
$wantMeta = (-not $NoFafoMeta) -and ($Force -or $Restart -or $prefs.startWithOneClick.fafoMetaServer)

Write-Srv ""
Write-Srv " FAFO companion servers (hidden / no console windows)" 'Cyan'
Write-Srv "   S1 = HTML Toolbox Server (media/Verifone/tools)" 'DarkGray'
Write-Srv "   S2 = FAFO Local Media Tagger (Chrome extension)" 'DarkGray'
Write-Srv " Root: $ToolboxRoot"

if ($Restart) {
    Write-Srv " Restart requested — stopping listeners first..." 'Yellow'
    if ($wantToolbox) { Stop-ListenerOnPort $tbPort }
    if ($wantMeta) { Stop-ListenerOnPort 8765 }
    Start-Sleep -Milliseconds 700
}

$started = @()
$pyServer = Get-ServerPython
if (-not $pyServer -and ($wantToolbox -or $wantMeta)) {
    throw "Missing .venv — run INSTALL-PYTHON.bat first"
}

# --- S1 HTML Toolbox Server ---
if ($wantToolbox) {
    if (Test-HttpOk $tbHealth) {
        Write-Srv " [OK] S1 HTML Toolbox already online @ ${tbHost}:${tbPort}" 'Green'
        $started += [pscustomobject]@{ id = 'toolbox'; ok = $true; already = $true }
    } else {
        Write-Srv " Starting S1 HTML Toolbox Server (hidden)..." 'Yellow'
        $serverPy = Join-Path $ToolboxRoot 'server\aitoolbox_server.py'
        if (-not (Test-Path -LiteralPath $serverPy)) { throw "Missing $serverPy" }
        try {
            $null = Start-HiddenProcess -FilePath $pyServer -ArgumentList @($serverPy) -WorkingDirectory (Join-Path $ToolboxRoot 'server')
            $started += [pscustomobject]@{ id = 'toolbox'; ok = $true; started = $true; hidden = $true }
        } catch {
            Write-Srv " [!] S1 HTML Toolbox start failed: $($_.Exception.Message)" 'Red'
            $started += [pscustomobject]@{ id = 'toolbox'; ok = $false; error = $_.Exception.Message }
        }
    }
} else {
    Write-Srv " [SKIP] S1 HTML Toolbox (disabled in launch prefs)" 'DarkGray'
}

# --- S2 FAFO Local Media Tagger ---
if ($wantMeta) {
    if (Test-HttpOk $metaHealth) {
        Write-Srv " [OK] S2 FAFO Local Media Tagger already online @ 127.0.0.1:8765" 'Green'
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
