# Install-FAFOToolbox.ps1
# Professional first-run installer for AI HTML Toolbox / FAFO.
#
# Checks what is already installed, runs only what is missing, and leaves
# Desktop + Start Menu shortcuts so users never hunt the install folder.
#
# No admin / UAC required (current-user protocol, shortcuts, local .venv).
#
# Usage:
#   .\Scripts\Install-FAFOToolbox.ps1
#   .\Scripts\Install-FAFOToolbox.ps1 -Silent -Launch
#   .\Scripts\Install-FAFOToolbox.ps1 -Repair
#   Double-click:  "Install FAFO Toolbox.bat"

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [switch]$Silent,
    [switch]$Quiet,
    [switch]$Launch,
    [switch]$Repair,
    [switch]$EnableWindowsStartup,
    [switch]$SkipLaunchPrompt,
    [switch]$AsObject
)

$ErrorActionPreference = 'Stop'
$isQuiet = $Quiet -or $Silent

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}
$ToolboxRoot = (Resolve-Path -LiteralPath $ToolboxRoot).Path
$env:FAFO_TOOLBOX_ROOT = $ToolboxRoot

function Write-Install([string]$Message, [string]$Color = 'White') {
    if (-not $isQuiet) {
        Write-Host $Message -ForegroundColor $Color
    }
}

function Write-Banner {
    if ($isQuiet) { return }
    $ver = '1.x'
    $vf = Join-Path $ToolboxRoot 'VERSION'
    if (Test-Path -LiteralPath $vf) {
        try { $ver = (Get-Content -LiteralPath $vf -Raw).Trim() } catch {}
    }
    Write-Host ""
    Write-Host "  ========================================================" -ForegroundColor Cyan
    Write-Host "   AI HTML TOOLBOX  /  FAFO   -   Installer" -ForegroundColor Cyan
    Write-Host "   Version $ver" -ForegroundColor DarkCyan
    Write-Host "  ========================================================" -ForegroundColor Cyan
    Write-Host "   One-time setup for this PC. No admin rights needed." -ForegroundColor DarkGray
    Write-Host "   Root: $ToolboxRoot" -ForegroundColor DarkGray
    Write-Host ""
}

function Get-Status {
    $s = & (Join-Path $PSScriptRoot 'Get-FAFOSetupStatus.ps1') -ToolboxRoot $ToolboxRoot -AsObject
    if ($s -is [System.Array]) { $s = $s | Select-Object -First 1 }
    return $s
}

function Show-Status([object]$Status, [string]$Title = 'Installation check') {
    if ($isQuiet) { return }
    Write-Install "  $Title" 'Cyan'
    Write-Install "  --------------------------------------------------------" 'DarkGray'
    $rows = @(
        @{ ok = $Status.checks.chromeFound;        label = 'Google Chrome' }
        @{ ok = $Status.checks.venvPython -and $Status.checks.venvImportsOk; label = 'Python environment (.venv)' }
        @{ ok = $Status.checks.protocolRegistered; label = 'aitoolbox:// protocol (Start from browser)' }
        @{ ok = $Status.checks.desktopShortcut;    label = 'Desktop shortcuts' }
        @{ ok = $Status.checks.markerPresent;      label = 'Setup completion marker' }
        @{ ok = $Status.checks.launcherHtml;       label = 'Toolbox files present' }
    )
    $sm = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AI HTML Toolbox\AI HTML Toolbox.lnk'
    $rows += @{ ok = (Test-Path -LiteralPath $sm); label = 'Start Menu shortcuts' }
    $startSrv = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AI HTML Toolbox - Start Servers.lnk'
    $rows += @{ ok = (Test-Path -LiteralPath $startSrv); label = 'Desktop "Start Servers" shortcut' }

    foreach ($r in $rows) {
        if ($r.ok) {
            Write-Install ("    [OK]  " + $r.label) 'Green'
        } else {
            Write-Install ("    [  ]  " + $r.label) 'Yellow'
        }
    }
    Write-Install ""
    if ($Status.complete -and -not $Repair) {
        Write-Install "  Status: READY  (already installed on this PC)" 'Green'
    } elseif ($Status.readyToLaunch) {
        Write-Install "  Status: Almost ready  (will finish remaining steps)" 'Yellow'
    } else {
        Write-Install "  Status: Needs setup" 'Yellow'
    }
    Write-Install ""
}

function Test-VenvReady {
    $py = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) { return $false }
    try {
        $null = & $py -c "import fastapi, uvicorn, psutil" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Invoke-Step([string]$Name, [scriptblock]$Action) {
    Write-Install "  -> $Name..." 'Cyan'
    try {
        & $Action
        Write-Install "     [OK] $Name" 'Green'
        return $true
    } catch {
        Write-Install "     [FAIL] $Name : $($_.Exception.Message)" 'Red'
        return $false
    }
}

# --- Main ---
Write-Banner

$status = Get-Status
Show-Status $status 'Before install'

if ($status.complete -and -not $Repair) {
    Write-Install "  Everything needed is already installed." 'Green'
    Write-Install "  Use Desktop:  AI HTML Toolbox" 'DarkGray'
    Write-Install "  Or:           AI HTML Toolbox - Start Servers" 'DarkGray'
    Write-Install ""
    if (-not $isQuiet -and -not $SkipLaunchPrompt -and -not $Launch) {
        $ans = Read-Host "  Launch the Toolbox now? [Y/n]"
        if ($ans -eq '' -or $ans -match '^[Yy]') { $Launch = $true }
    }
    if ($Launch) {
        $launchBat = Join-Path $ToolboxRoot 'Launch-AI-HTML-Toolbox.bat'
        if (Test-Path -LiteralPath $launchBat) {
            Start-Process -FilePath $launchBat -WorkingDirectory $ToolboxRoot
            Write-Install "  Launching..." 'Cyan'
        }
    }
    if (-not $isQuiet) {
        Write-Install ""
        Write-Install "  Tip: re-run with  Install FAFO Toolbox.bat  and choose Repair if something broke." 'DarkGray'
        Write-Install ""
    }
    if ($AsObject) {
        return [pscustomobject]@{ ok = $true; complete = $true; alreadyInstalled = $true; toolboxRoot = $ToolboxRoot }
    }
    exit 0
}

if ($Repair) {
    Write-Install "  Repair mode: re-running install steps..." 'Yellow'
    Write-Install ""
}

$failed = $false
$stepsOk = 0
$stepsFail = 0

# 1) Chrome (cannot install silently for user — just detect)
Write-Install "  [1/6] Google Chrome" 'Cyan'
if ($status.chromePath) {
    Write-Install "     [OK] Found: $($status.chromePath)" 'Green'
    $stepsOk++
} else {
    Write-Install "     [FAIL] Google Chrome not found." 'Red'
    Write-Install "            Install Chrome from https://www.google.com/chrome/ then re-run this installer." 'Yellow'
    Write-Install "            (Edge is not used for the app shell.)" 'DarkGray'
    $failed = $true
    $stepsFail++
}
Write-Install ""

# 2) Python venv + packages
Write-Install "  [2/6] Python environment" 'Cyan'
if (-not $Repair -and (Test-VenvReady)) {
    Write-Install "     [OK] Already ready (.venv)" 'Green'
    $stepsOk++
} else {
    $installPy = Join-Path $PSScriptRoot 'Install-PythonEnvironment.ps1'
    if (-not (Test-Path -LiteralPath $installPy)) {
        Write-Install "     [FAIL] Missing Install-PythonEnvironment.ps1" 'Red'
        $failed = $true
        $stepsFail++
    } else {
        try {
            $p = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', $installPy,
                '-ToolboxRoot', $ToolboxRoot
            ) -Wait -PassThru -WindowStyle $(if ($isQuiet) { 'Hidden' } else { 'Normal' })
            if ($p.ExitCode -ne 0) { throw "Install-PythonEnvironment exit $($p.ExitCode)" }
            if (-not (Test-VenvReady)) { throw "venv imports still failing" }
            Write-Install "     [OK] Python .venv ready" 'Green'
            $stepsOk++
        } catch {
            Write-Install "     [FAIL] $($_.Exception.Message)" 'Red'
            $failed = $true
            $stepsFail++
        }
    }
}
Write-Install ""

# 3-5) Protocol + shortcuts + marker via Complete-FAFOSetup
Write-Install "  [3/6] Protocol, shortcuts, setup marker" 'Cyan'
$completeScript = Join-Path $PSScriptRoot 'Complete-FAFOSetup.ps1'
try {
    $cargs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', $completeScript,
        '-ToolboxRoot', $ToolboxRoot
    )
    if ($isQuiet) { $cargs += '-Quiet' }
    if ($Repair) { $cargs += '-ForcePython' }
    $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $cargs -Wait -PassThru -WindowStyle $(if ($isQuiet) { 'Hidden' } else { 'Normal' })
    # Complete-FAFOSetup exit 0 = complete, 2 = incomplete
    if ($p.ExitCode -eq 0) {
        Write-Install "     [OK] Core setup complete" 'Green'
        $stepsOk++
    } elseif ($p.ExitCode -eq 2) {
        Write-Install "     [!] Core setup ran but still incomplete (see messages above)" 'Yellow'
        $failed = $true
        $stepsFail++
    } else {
        throw "Complete-FAFOSetup exit $($p.ExitCode)"
    }
} catch {
    Write-Install "     [FAIL] $($_.Exception.Message)" 'Red'
    $failed = $true
    $stepsFail++
}
Write-Install ""

# 4) Ensure Start Menu + Start Servers shortcuts (extra polish)
Write-Install "  [4/6] Desktop + Start Menu launchers" 'Cyan'
$sc = Join-Path $ToolboxRoot 'Install-Desktop-Shortcut.ps1'
if (Test-Path -LiteralPath $sc) {
    try {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', $sc, '-StartMenu'
        ) -Wait -PassThru -WindowStyle Hidden
        if ($p.ExitCode -ne 0) { throw "exit $($p.ExitCode)" }
        Write-Install "     [OK] AI HTML Toolbox  +  Start Servers  shortcuts" 'Green'
        $stepsOk++
    } catch {
        Write-Install "     [!] Shortcuts: $($_.Exception.Message)" 'Yellow'
        $stepsFail++
    }
} else {
    Write-Install "     [!] Install-Desktop-Shortcut.ps1 missing" 'Yellow'
}
Write-Install ""

# 5) Default launch prefs (companions on, hidden servers)
Write-Install "  [5/6] Default server preferences" 'Cyan'
try {
    $prefsDir = Join-Path $env:LOCALAPPDATA 'FAFO'
    if (-not (Test-Path -LiteralPath $prefsDir)) {
        New-Item -ItemType Directory -Path $prefsDir -Force | Out-Null
    }
    $prefsPath = Join-Path $prefsDir 'launch-prefs.json'
    $prefs = @{
        version           = 1
        startWithOneClick = @{ toolboxServer = $true; fafoMetaServer = $true }
        windowsStartup    = @{ servers = $false; app = $false }
        fafoMetaRoot      = $null
        updatedAt         = (Get-Date).ToString('o')
    }
    if (Test-Path -LiteralPath $prefsPath) {
        try {
            $existing = Get-Content -LiteralPath $prefsPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($existing.fafoMetaRoot) { $prefs.fafoMetaRoot = [string]$existing.fafoMetaRoot }
            if ($existing.windowsStartup) {
                $prefs.windowsStartup = @{
                    servers = [bool]$existing.windowsStartup.servers
                    app     = [bool]$existing.windowsStartup.app
                }
            }
        } catch {}
    }
    # Seed explorer-meta path if discoverable
    $metaCandidates = @(
        'D:\Chrome python_HTML AI apps\FAFO Ultimate Tab\explorer-meta'
        (Join-Path $env:USERPROFILE 'Desktop\FAFO Ultimate Tab\explorer-meta')
    )
    if (-not $prefs.fafoMetaRoot) {
        foreach ($c in $metaCandidates) {
            if ($c -and (Test-Path -LiteralPath (Join-Path $c 'server.py'))) {
                $prefs.fafoMetaRoot = (Resolve-Path -LiteralPath $c).Path
                break
            }
        }
    }
    ($prefs | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $prefsPath -Encoding UTF8
    Write-Install "     [OK] Companions enabled for one-click (toolbox + FAFO tags)" 'Green'
    $stepsOk++
} catch {
    Write-Install "     [!] Prefs: $($_.Exception.Message)" 'Yellow'
}
Write-Install ""

# 6) Optional Windows startup + first server start
Write-Install "  [6/6] Background servers + Windows startup" 'Cyan'
$doWinStart = $EnableWindowsStartup
if (-not $isQuiet -and -not $EnableWindowsStartup -and -not $SkipLaunchPrompt) {
    $ans = Read-Host "  Start servers automatically when Windows signs in? [y/N]"
    if ($ans -match '^[Yy]') { $doWinStart = $true }
}

if ($doWinStart) {
    try {
        $startup = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\FAFO Toolbox Servers.lnk'
        $ps1 = Join-Path $ToolboxRoot 'Scripts\Start-FAFOServers.ps1'
        if (-not (Test-Path -LiteralPath $ps1)) { throw "Missing Start-FAFOServers.ps1" }
        # Remove legacy tray-only shortcut if present
        $legacy = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\AI Toolbox Server.lnk'
        if (Test-Path -LiteralPath $legacy) { Remove-Item -LiteralPath $legacy -Force -ErrorAction SilentlyContinue }
        $w = New-Object -ComObject WScript.Shell
        $l = $w.CreateShortcut($startup)
        $l.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $l.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`" -ToolboxRoot `"$ToolboxRoot`" -Quiet"
        $l.WorkingDirectory = $ToolboxRoot
        $l.WindowStyle = 7
        $l.Description = 'FAFO Toolbox companion servers (hidden + tray watchdog)'
        $ico = Join-Path $ToolboxRoot 'assets\AI-HTML-Toolbox.ico'
        if (Test-Path -LiteralPath $ico) { $l.IconLocation = "$ico,0" }
        $l.Save()
        Write-Install "     [OK] Windows Startup: servers (background + tray)" 'Green'
    } catch {
        Write-Install "     [!] Windows startup: $($_.Exception.Message)" 'Yellow'
    }
} else {
    Write-Install "     [OK] Skipped (you can enable later in Launcher)" 'DarkGray'
}

# First start of companions (hidden) so first app open is green
try {
    $startPs1 = Join-Path $PSScriptRoot 'Start-FAFOServers.ps1'
    if ((Test-Path -LiteralPath $startPs1) -and (Test-VenvReady)) {
        Write-Install "     Starting background servers + tray (first time)..." 'DarkGray'
        $null = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden',
            '-File', $startPs1, '-ToolboxRoot', $ToolboxRoot, '-Quiet', '-HealthTimeoutSec', '20'
        ) -WindowStyle Hidden
        Write-Install "     [OK] Servers starting in background (tray will appear)" 'Green'
    }
} catch {
    Write-Install "     [i] Servers will start on first Launch" 'DarkGray'
}
Write-Install ""

# Final status
$final = Get-Status
Show-Status $final 'After install'

Write-Install "  ========================================================" 'Cyan'
if ($final.complete -or $final.readyToLaunch) {
    Write-Install "   INSTALL COMPLETE" 'Green'
    Write-Install ""
    Write-Install "   How to use every day (no install folder needed):" 'White'
    Write-Install "     1. Desktop:  AI HTML Toolbox           (app + servers)" 'Cyan'
    Write-Install "     2. Desktop:  AI HTML Toolbox - Start Servers  (if offline)" 'Cyan'
    Write-Install "     3. Start Menu > AI HTML Toolbox" 'Cyan'
    Write-Install "     4. System tray icon: Restart / Open Launcher" 'Cyan'
    Write-Install ""
    Write-Install "   Servers stay hidden and auto-restart while the tray/app is open." 'DarkGray'
} else {
    Write-Install "   INSTALL INCOMPLETE" 'Red'
    Write-Install "   Missing:" 'Yellow'
    foreach ($m in @($final.missing)) {
        Write-Install "     - $m" 'Yellow'
    }
    Write-Install "   Fix the items above and run this installer again." 'Yellow'
}
Write-Install "  ========================================================" 'Cyan'
Write-Install ""

if (($final.complete -or $final.readyToLaunch) -and -not $isQuiet -and -not $SkipLaunchPrompt -and -not $Launch) {
    $ans = Read-Host "  Launch AI HTML Toolbox now? [Y/n]"
    if ($ans -eq '' -or $ans -match '^[Yy]') { $Launch = $true }
}

if ($Launch -and ($final.complete -or $final.readyToLaunch)) {
    $launchBat = Join-Path $ToolboxRoot 'Launch-AI-HTML-Toolbox.bat'
    if (Test-Path -LiteralPath $launchBat) {
        Start-Process -FilePath $launchBat -WorkingDirectory $ToolboxRoot
        Write-Install "  Launching..." 'Cyan'
    }
}

if ($AsObject) {
    return [pscustomobject]@{
        ok            = [bool]($final.complete -or $final.readyToLaunch)
        complete      = [bool]$final.complete
        readyToLaunch = [bool]$final.readyToLaunch
        toolboxRoot   = $ToolboxRoot
        failed        = $failed
    }
}

if ($final.complete -or $final.readyToLaunch) { exit 0 } else { exit 2 }
