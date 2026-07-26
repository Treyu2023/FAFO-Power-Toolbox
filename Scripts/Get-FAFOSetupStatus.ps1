# Get-FAFOSetupStatus.ps1
# Machine-local setup status for AI HTML Toolbox / FAFO.
# Marker: %LOCALAPPDATA%\FAFO\Setup\setup-state.json
#
# Exit codes: 0 = complete, 2 = incomplete, 1 = hard error
# stdout: JSON

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [switch]$AsObject
)

$ErrorActionPreference = 'Continue'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

try {
    $ToolboxRoot = (Resolve-Path -LiteralPath $ToolboxRoot -ErrorAction Stop).Path
} catch {
    $result = [ordered]@{
        complete      = $false
        readyToLaunch = $false
        toolboxRoot   = $null
        reason        = "Toolbox root not found: $($_.Exception.Message)"
        checks        = [ordered]@{}
        missing       = @('Toolbox root')
        chromePath    = $null
        venvPython    = $null
        markerPath    = $null
        completedAt   = $null
        server        = [ordered]@{ listening = $false; endpoint = 'http://127.0.0.87:18765' }
    }
    if ($AsObject) { return [pscustomobject]$result }
    $result | ConvertTo-Json -Depth 8 -Compress
    exit 1
}

$setupDir    = Join-Path $env:LOCALAPPDATA 'FAFO\Setup'
$markerPath  = Join-Path $setupDir 'setup-state.json'
$venvPy      = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
$launcherHtml = Join-Path $ToolboxRoot 'Toolbox Launcher.html'
$launchBat   = Join-Path $ToolboxRoot 'Launch-AI-HTML-Toolbox.bat'
$protocolBat = Join-Path $ToolboxRoot 'server\protocol_start.bat'
$bindFile    = Join-Path $ToolboxRoot 'shared\aitoolbox-bind.json'
$desktopLnk  = Join-Path ([Environment]::GetFolderPath('Desktop')) 'AI HTML Toolbox.lnk'

function Test-PythonImportsOk([string]$Exe) {
    if (-not $Exe -or -not (Test-Path -LiteralPath $Exe)) { return $false }
    try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Stop'
        $null = & $Exe -c "import fastapi, uvicorn, psutil" 2>$null
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        return ($code -eq 0)
    } catch {
        return $false
    }
}

function Find-ChromePath {
    $candidates = New-Object System.Collections.Generic.List[string]
    try {
        $where = & where.exe chrome 2>$null
        if ($where) {
            foreach ($line in @($where)) {
                if ($line) { [void]$candidates.Add($line.Trim()) }
            }
        }
    } catch {}
    foreach ($c in @(
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:ProgramFiles 'Google\Chrome Beta\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome Beta\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome SxS\Application\chrome.exe')
    )) {
        if ($c) { [void]$candidates.Add($c) }
    }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    return $null
}

function Test-ProtocolRegistered([string]$Root) {
    try {
        $cmd = Get-ItemProperty -Path 'HKCU:\Software\Classes\aitoolbox\shell\open\command' -ErrorAction SilentlyContinue
        if (-not $cmd -or -not $cmd.'(default)') { return $false }
        $cmdLine = [string]$cmd.'(default)'
        return ($cmdLine -like '*protocol_start.bat*' -or $cmdLine -like '*aitoolbox*')
    } catch {
        return $false
    }
}

function Test-ServerListening([string]$Root) {
    $hostAddr = '127.0.0.87'
    $port = 18765
    $bindFile = Join-Path $Root 'shared\aitoolbox-bind.json'
    if (Test-Path -LiteralPath $bindFile) {
        try {
            $bind = Get-Content -LiteralPath $bindFile -Raw | ConvertFrom-Json
            if ($bind.host) { $hostAddr = [string]$bind.host }
            if ($bind.port) { $port = [int]$bind.port }
        } catch {}
    }
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $iar = $client.BeginConnect($hostAddr, $port, $null, $null)
            $ok = $iar.AsyncWaitHandle.WaitOne(400, $false)
            if ($ok -and $client.Connected) { return $true }
            return $false
        } finally {
            $client.Close()
        }
    } catch {
        return $false
    }
}

$venvPy = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
$chromePath = Find-ChromePath
$venvImportsOk = Test-PythonImportsOk $venvPy
$protocolOk = Test-ProtocolRegistered $ToolboxRoot
$serverUp = Test-ServerListening $ToolboxRoot

$markerComplete = $false
$completedAt = $null
if (Test-Path -LiteralPath $markerPath) {
    try {
        $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
        $markerComplete = [bool]$marker.complete
        $completedAt = $marker.completedAt
    } catch {
        $markerComplete = $false
    }
}

$lastRunPath = Join-Path $setupDir 'last-setup-run.json'
$lastRunSummary = $null
if (Test-Path -LiteralPath $lastRunPath) {
    try {
        $lr = Get-Content -LiteralPath $lastRunPath -Raw | ConvertFrom-Json
        $lastRunSummary = [ordered]@{
            ok       = [bool]$lr.ok
            complete = [bool]$lr.complete
            ranAt    = $lr.ranAt
            failed   = [bool]$lr.failed
        }
    } catch {
        $lastRunSummary = $null
    }
}

$checks = [ordered]@{
    toolboxRoot        = $true
    launcherHtml       = (Test-Path -LiteralPath $launcherHtml)
    launchBat          = (Test-Path -LiteralPath $launchBat)
    protocolBat        = (Test-Path -LiteralPath $protocolBat)
    venvPython         = (Test-Path -LiteralPath $venvPy)
    venvImportsOk      = $venvImportsOk
    protocolRegistered = $protocolOk
    chromeFound        = [bool]$chromePath
    desktopShortcut    = (Test-Path -LiteralPath $desktopLnk)
    serverListening    = $serverUp
    markerPresent      = $markerComplete
    lastRunLogged      = [bool]$lastRunSummary
}

$criticalOk = $checks.launcherHtml -and $checks.launchBat -and $checks.protocolBat -and
              $checks.venvPython -and $checks.venvImportsOk -and $checks.protocolRegistered -and
              $checks.chromeFound

$complete = [bool]($criticalOk -and $markerComplete)

$missing = New-Object System.Collections.Generic.List[string]
if (-not $checks.venvPython -or -not $checks.venvImportsOk) { [void]$missing.Add('Python virtual environment (.venv)') }
if (-not $checks.protocolRegistered) { [void]$missing.Add('aitoolbox:// protocol registration') }
if (-not $checks.chromeFound) { [void]$missing.Add('Google Chrome') }
if (-not $checks.desktopShortcut) { [void]$missing.Add('Desktop shortcut (optional)') }
if (-not $checks.markerPresent) { [void]$missing.Add('First-run setup completion marker') }

$result = [ordered]@{
    complete      = $complete
    readyToLaunch = [bool]$criticalOk
    showFirstRun  = -not $complete
    toolboxRoot   = $ToolboxRoot
    chromePath    = $chromePath
    venvPython    = $(if (Test-Path -LiteralPath $venvPy) { $venvPy } else { $null })
    markerPath    = $markerPath
    lastRunPath   = $lastRunPath
    completedAt   = $completedAt
    lastRun       = $lastRunSummary
    checks        = $checks
    missing       = @($missing)
    server        = [ordered]@{
        listening = $serverUp
        endpoint  = 'http://127.0.0.87:18765'
    }
}

if ($AsObject) { return [pscustomobject]$result }
$result | ConvertTo-Json -Depth 8 -Compress
if ($complete) { exit 0 } else { exit 2 }
