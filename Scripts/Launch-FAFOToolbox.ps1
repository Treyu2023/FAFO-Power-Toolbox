# Launch-FAFOToolbox.ps1
# One-click: ensure setup -> start server -> open Chrome app window (never Edge).
# Thin shell: Chrome --app mode. Optional -TopMost for always-on-top.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [string]$Page = 'Toolbox Launcher.html',
    [switch]$TopMost,
    [switch]$SkipSetup,
    [switch]$NoServer,
    [int]$HealthTimeoutSec = 45
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}
$ToolboxRoot = (Resolve-Path -LiteralPath $ToolboxRoot).Path
$env:FAFO_TOOLBOX_ROOT = $ToolboxRoot

function Write-Launch([string]$Message, [string]$Color = 'Cyan') {
    Write-Host $Message -ForegroundColor $Color
}

function Get-Status {
    # Same-process call - nested powershell -File loses -AsObject return values
    $s = & (Join-Path $PSScriptRoot 'Get-FAFOSetupStatus.ps1') -ToolboxRoot $ToolboxRoot -AsObject
    if ($s -is [System.Array]) { $s = $s | Select-Object -First 1 }
    return $s
}

function Test-HealthEndpoint {
    $endpoint = 'http://127.0.0.87:18765/api/health'
    $bindFile = Join-Path $ToolboxRoot 'shared\aitoolbox-bind.json'
    if (Test-Path -LiteralPath $bindFile) {
        try {
            $bind = Get-Content -LiteralPath $bindFile -Raw | ConvertFrom-Json
            if ($bind.host -and $bind.port) {
                $endpoint = "http://$($bind.host):$($bind.port)/api/health"
            }
        } catch {}
    }
    try {
        $resp = Invoke-WebRequest -Uri $endpoint -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300)
    } catch {
        return $false
    }
}

function Start-ToolboxServer {
    # S1 only — HTML Toolbox lifecycle. S2 (Ultimate Tab) starts with Chrome, not here.
    $multi = Join-Path $PSScriptRoot 'Start-FAFOServers.ps1'
    if (Test-Path -LiteralPath $multi) {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', $multi,
            '-ToolboxRoot', $ToolboxRoot,
            '-NoFafoMeta',
            '-Force',
            '-HealthTimeoutSec', ([Math]::Max(8, [int]($HealthTimeoutSec / 2))),
            '-Quiet'
        ) -Wait -PassThru -WindowStyle Hidden
        if ($p.ExitCode -ne 0) {
            Write-Launch " [i] S1 start helper exit $($p.ExitCode) — falling back to toolbox-only" 'DarkGray'
        } else {
            return
        }
    }
    # Mark toolbox session + clear S1 sleep via launch_ops when possible
    $venvPy = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
    $ops = Join-Path $ToolboxRoot 'server\launch_ops.py'
    if ((Test-Path -LiteralPath $venvPy) -and (Test-Path -LiteralPath $ops)) {
        Start-Process -FilePath $venvPy -ArgumentList @(
            '-c',
            "import sys; sys.path.insert(0, r'$($ToolboxRoot)\server'); import launch_ops; launch_ops.wake_companions(toolbox=True, fafo_meta=False, wait_sec=10)"
        ) -WorkingDirectory $ToolboxRoot -WindowStyle Hidden -Wait | Out-Null
        return
    }
    $startBat = Join-Path $ToolboxRoot '1-Start-HTML-Toolbox-Server.bat'
    if (Test-Path -LiteralPath $startBat) {
        Start-Process -FilePath $startBat -WorkingDirectory $ToolboxRoot -WindowStyle Minimized
        return
    }
    if (-not (Test-Path -LiteralPath $venvPy)) {
        throw "Server python not found: $venvPy"
    }
    Start-Process -FilePath $venvPy -ArgumentList @('aitoolbox_server.py') -WorkingDirectory (Join-Path $ToolboxRoot 'server') -WindowStyle Minimized
}

function Test-MetaHealthEndpoint {
    try {
        $resp = Invoke-WebRequest -Uri 'http://127.0.0.1:8765/api/health' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300)
    } catch {
        return $false
    }
}

function Set-ChromeTopMost {
    Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class FafoWin32 {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
  public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
  public const uint SWP_NOSIZE = 0x0001;
  public const uint SWP_NOMOVE = 0x0002;
  public const uint SWP_SHOWWINDOW = 0x0040;
}
"@ -ErrorAction SilentlyContinue

    Start-Sleep -Milliseconds 1000
    $procs = @(Get-Process -Name chrome -ErrorAction SilentlyContinue)
    if (-not $procs -or $procs.Count -eq 0) { return }

    $candidates = New-Object System.Collections.Generic.List[IntPtr]
    $handler = [FafoWin32+EnumProc]{
        param([IntPtr]$hWnd, [IntPtr]$lParam)
        if (-not [FafoWin32]::IsWindowVisible($hWnd)) { return $true }
        $pid = [uint32]0
        [void][FafoWin32]::GetWindowThreadProcessId($hWnd, [ref]$pid)
        $match = $false
        foreach ($p in $procs) {
            if ([uint32]$p.Id -eq $pid) { $match = $true; break }
        }
        if (-not $match) { return $true }
        $sb = New-Object System.Text.StringBuilder 512
        [void][FafoWin32]::GetWindowText($hWnd, $sb, $sb.Capacity)
        $title = $sb.ToString()
        if ($title -match 'AI HTML|TOOLBOX|Toolbox|Media Library|Universal Converter|FAFO|Task Manager') {
            [void]$candidates.Add($hWnd)
        }
        return $true
    }
    [void][FafoWin32]::EnumWindows($handler, [IntPtr]::Zero)
    foreach ($hwnd in $candidates) {
        [void][FafoWin32]::SetWindowPos(
            $hwnd,
            [FafoWin32]::HWND_TOPMOST,
            0, 0, 0, 0,
            [FafoWin32]::SWP_NOMOVE -bor [FafoWin32]::SWP_NOSIZE -bor [FafoWin32]::SWP_SHOWWINDOW
        )
    }
}

Write-Launch ""
Write-Launch " AI HTML TOOLBOX - One-click launch" 'Cyan'
Write-Launch " Root: $ToolboxRoot"

# --- Setup if needed ---
$status = Get-Status
if (-not $SkipSetup) {
    if (-not $status.complete) {
        Write-Launch " Setup incomplete - running automated setup..." 'Yellow'
        $setupScript = Join-Path $PSScriptRoot 'Complete-FAFOSetup.ps1'
        $setupArgs = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', $setupScript,
            '-ToolboxRoot', $ToolboxRoot,
            '-Quiet'
        )
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $setupArgs -Wait -PassThru -WindowStyle Hidden
        $status = Get-Status
        if (-not $status.readyToLaunch) {
            Write-Launch " Setup still incomplete:" 'Red'
            foreach ($m in @($status.missing)) { Write-Launch "   - $m" 'Yellow' }
            if (-not $status.chromePath) {
                Write-Launch " Google Chrome is required (Edge will not be used)." 'Red'
                exit 1
            }
            if (-not $status.checks.venvImportsOk) {
                Write-Launch " Python venv is not ready. Run INSTALL-PYTHON.bat" 'Red'
                exit 1
            }
        } else {
            Write-Launch " [OK] Setup ready" 'Green'
        }
    } else {
        Write-Launch " [OK] Setup complete" 'Green'
    }
} else {
    Write-Launch " [SKIP] Setup check" 'Yellow'
}

# --- Chrome only ---
$chrome = $status.chromePath
if (-not $chrome -or -not (Test-Path -LiteralPath $chrome)) {
    Write-Launch " Google Chrome not found. Install Chrome (Edge will not be used)." 'Red'
    exit 1
}
Write-Launch " [OK] Chrome: $chrome" 'Green'

# --- S1 only (HTML Toolbox). S2 Ultimate Tab starts when Chrome browser runs. ---
if (-not $NoServer) {
    $tbUp = Test-HealthEndpoint
    if (-not $tbUp) {
        Write-Launch " Starting S1 HTML Toolbox server (not S2 — that follows Chrome)..." 'Yellow'
        Start-ToolboxServer
        $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 800
            $tbUp = Test-HealthEndpoint
            if ($tbUp) { break }
        }
        if ($tbUp) {
            Write-Launch " [OK] S1 HTML Toolbox online (127.0.0.87:18765)" 'Green'
        } else {
            Write-Launch " [!] S1 did not become healthy in ${HealthTimeoutSec}s - opening UI anyway" 'Yellow'
        }
    } else {
        Write-Launch " [OK] S1 HTML Toolbox already online" 'Green'
        # Still mark toolbox session so watchdog keeps S1 while you use it
        $venvPy = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
        if (Test-Path -LiteralPath $venvPy) {
            Start-Process -FilePath $venvPy -ArgumentList @(
                '-c',
                "import sys; sys.path.insert(0, r'$($ToolboxRoot)\server'); import launch_ops; launch_ops.set_toolbox_session(True); launch_ops.set_servers_sleeping(toolbox=False)"
            ) -WorkingDirectory $ToolboxRoot -WindowStyle Hidden | Out-Null
        }
    }
    if (Test-MetaHealthEndpoint) {
        Write-Launch " [i] S2 Ultimate Tab tagger already up (Chrome lifecycle) @ 127.0.0.1:8765" 'DarkGray'
    } else {
        Write-Launch " [i] S2 Ultimate Tab starts with Chrome — not started by Toolbox" 'DarkGray'
    }
}

# --- Launch Chrome app window (thin shell) ---
# Prefer S1 HTTP origin so tools resolve under /toolbox/... (file:// breaks
# private-network fetches and relative app paths look "missing").
# Keep #tab / ?query off the filesystem path and out of percent-encoding
# (EscapeDataString("#") => %23 was the Duplicates 404).
$relPage = ($Page -replace '\\', '/').TrimStart('/')
$pageHash = ''
$pageQuery = ''
$hashAt = $relPage.IndexOf('#')
if ($hashAt -ge 0) {
    $pageHash = $relPage.Substring($hashAt)
    $relPage = $relPage.Substring(0, $hashAt)
}
$qAt = $relPage.IndexOf('?')
if ($qAt -ge 0) {
    $pageQuery = $relPage.Substring($qAt)
    $relPage = $relPage.Substring(0, $qAt)
}
$pagePath = Join-Path $ToolboxRoot ($relPage -replace '/', [IO.Path]::DirectorySeparatorChar)
if (-not (Test-Path -LiteralPath $pagePath)) {
    if (Test-Path -LiteralPath $relPage) {
        $pagePath = (Resolve-Path -LiteralPath $relPage).Path
    } else {
        throw "Page not found: $relPage"
    }
}

$appUrl = $null
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
if (Test-HealthEndpoint) {
    $encoded = ($relPage -split '/' | Where-Object { $_ } | ForEach-Object { [uri]::EscapeDataString($_) }) -join '/'
    $appUrl = "http://${tbHost}:${tbPort}/toolbox/$encoded$pageQuery$pageHash"
}

# Thin shell: Chrome --app mode (no browser chrome / tabs) + sensible default size
if ($appUrl) {
    Write-Launch " Opening Chrome thin shell via S1: $appUrl" 'Cyan'
    $appTarget = $appUrl
} else {
    Write-Launch " Opening Chrome thin shell via file (S1 offline): $pagePath" 'Yellow'
    $appTarget = $pagePath
}
$chromeArgs = @(
    "--app=`"$appTarget`"",
    '--new-window',
    '--window-size=1400,900',
    '--disable-features=TranslateUI'
)
Start-Process -FilePath $chrome -ArgumentList $chromeArgs -WorkingDirectory $ToolboxRoot | Out-Null

if ($TopMost) {
    Write-Launch " Applying always-on-top..." 'Yellow'
    try { Set-ChromeTopMost } catch { Write-Launch " [i] TopMost skipped: $($_.Exception.Message)" 'DarkGray' }
}

Write-Launch " [OK] Launched thin shell" 'Green'
Write-Launch "     Toolbox:  http://127.0.0.87:18765  (Verifone + media + system tools)" 'DarkGray'
Write-Launch "     FAFO tags: http://127.0.0.1:8765   (Local Tab companion, if found)" 'DarkGray'
exit 0
