# Complete-FAFOSetup.ps1
# Idempotent one-time setup: venv, protocol, desktop shortcut, setup marker.
# Marker: %LOCALAPPDATA%\FAFO\Setup\setup-state.json
# Last run: %LOCALAPPDATA%\FAFO\Setup\last-setup-run.json (always written)

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [switch]$Quiet,
    [switch]$SkipShortcut,
    [switch]$ForcePython,
    [switch]$AsObject
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}
$ToolboxRoot = (Resolve-Path -LiteralPath $ToolboxRoot).Path
$env:FAFO_TOOLBOX_ROOT = $ToolboxRoot

function Write-Setup([string]$Message, [string]$Color = 'Cyan') {
    if (-not $Quiet) {
        Write-Host $Message -ForegroundColor $Color
    }
}

function Test-VenvReady([string]$Root) {
    $py = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $py)) { return $false }
    try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Stop'
        $null = & $py -c "import fastapi, uvicorn, psutil" 2>$null
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        return ($code -eq 0)
    } catch {
        return $false
    }
}

$setupDir   = Join-Path $env:LOCALAPPDATA 'FAFO\Setup'
$markerPath = Join-Path $setupDir 'setup-state.json'
$lastRunPath = Join-Path $setupDir 'last-setup-run.json'
$steps = New-Object System.Collections.Generic.List[object]
$failed = $false

Write-Setup ""
Write-Setup " AI HTML TOOLBOX - Complete setup" 'Cyan'
Write-Setup " =================================" 'Cyan'
Write-Setup " Root: $ToolboxRoot"
Write-Setup ""

# --- 1) Python venv ---
Write-Setup " [1/4] Python virtual environment + packages"
$installScript = Join-Path $PSScriptRoot 'Install-PythonEnvironment.ps1'
try {
    if (-not $ForcePython -and (Test-VenvReady $ToolboxRoot)) {
        $steps.Add([ordered]@{ step = 'python_venv'; ok = $true; skipped = $true; reason = 'already ready' })
        Write-Setup " [OK] Python venv already ready (skipped install)" 'Green'
    } else {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass',
            '-File', $installScript,
            '-ToolboxRoot', $ToolboxRoot
        ) -Wait -PassThru -WindowStyle $(if ($Quiet) { 'Hidden' } else { 'Normal' })
        if ($p.ExitCode -ne 0) { throw "Install-PythonEnvironment.ps1 exit $($p.ExitCode)" }
        if (-not (Test-VenvReady $ToolboxRoot)) { throw "venv imports still failing after install" }
        $steps.Add([ordered]@{ step = 'python_venv'; ok = $true })
        Write-Setup " [OK] Python venv ready" 'Green'
    }
} catch {
    $failed = $true
    $steps.Add([ordered]@{ step = 'python_venv'; ok = $false; error = $_.Exception.Message })
    Write-Setup " [FAIL] Python venv: $($_.Exception.Message)" 'Red'
}

# --- 2) Protocol registration ---
Write-Setup ""
Write-Setup " [2/4] Register aitoolbox:// protocol"
try {
    $protocolBat = Join-Path $ToolboxRoot 'server\protocol_start.bat'
    if (-not (Test-Path -LiteralPath $protocolBat)) { throw "Missing protocol_start.bat" }
    $cmd = "`"$protocolBat`" `"%1`""
    $cmdKey = 'HKCU:\Software\Classes\aitoolbox\shell\open\command'
    $already = $false
    if (Test-Path -LiteralPath $cmdKey) {
        try {
            $existing = (Get-ItemProperty -Path $cmdKey -ErrorAction Stop).'(default)'
            if ($existing -and ("$existing" -like '*protocol_start.bat*')) { $already = $true }
        } catch { $already = $false }
    }
    if ($already) {
        $steps.Add([ordered]@{ step = 'protocol'; ok = $true; skipped = $true; reason = 'already registered' })
        Write-Setup " [OK] Protocol already registered" 'Green'
    } else {
        # PowerShell registry APIs (avoid reg.exe which can hang on some PCs)
        $base = 'HKCU:\Software\Classes\aitoolbox'
        if (-not (Test-Path -LiteralPath $base)) { New-Item -Path $base -Force | Out-Null }
        Set-ItemProperty -Path $base -Name '(default)' -Value 'URL:AI Toolbox Protocol' -Force
        New-ItemProperty -Path $base -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
        $iconKey = Join-Path $base 'DefaultIcon'
        if (-not (Test-Path -LiteralPath $iconKey)) { New-Item -Path $iconKey -Force | Out-Null }
        Set-ItemProperty -Path $iconKey -Name '(default)' -Value "$env:SystemRoot\System32\shell32.dll,13" -Force
        if (-not (Test-Path -LiteralPath $cmdKey)) { New-Item -Path $cmdKey -Force | Out-Null }
        Set-ItemProperty -Path $cmdKey -Name '(default)' -Value $cmd -Force
        $steps.Add([ordered]@{ step = 'protocol'; ok = $true })
        Write-Setup " [OK] Protocol registered" 'Green'
    }
    Write-Setup "      aitoolbox://start | console | folder | setup | launch" 'DarkGray'
} catch {
    $failed = $true
    $steps.Add([ordered]@{ step = 'protocol'; ok = $false; error = $_.Exception.Message })
    Write-Setup " [FAIL] Protocol: $($_.Exception.Message)" 'Red'
}

# --- 3) Desktop shortcut ---
Write-Setup ""
Write-Setup " [3/4] Desktop shortcut"
if ($SkipShortcut) {
    $steps.Add([ordered]@{ step = 'desktop_shortcut'; ok = $true; skipped = $true })
    Write-Setup " [SKIP] Desktop shortcut" 'Yellow'
} else {
    try {
        $shortcutScript = Join-Path $ToolboxRoot 'Install-Desktop-Shortcut.ps1'
        if (Test-Path -LiteralPath $shortcutScript) {
            $p = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
                '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $shortcutScript
            ) -Wait -PassThru -WindowStyle $(if ($Quiet) { 'Hidden' } else { 'Normal' })
            if ($p.ExitCode -ne 0) { throw "Install-Desktop-Shortcut.ps1 exit $($p.ExitCode)" }
        } else {
            $launchBat = Join-Path $ToolboxRoot 'Launch-AI-HTML-Toolbox.bat'
            $desktop = [Environment]::GetFolderPath('Desktop')
            $shortcutPath = Join-Path $desktop 'AI HTML Toolbox.lnk'
            $w = New-Object -ComObject WScript.Shell
            $sc = $w.CreateShortcut($shortcutPath)
            $sc.TargetPath = $launchBat
            $sc.WorkingDirectory = $ToolboxRoot
            $sc.WindowStyle = 7
            $sc.Description = 'AI HTML Toolbox - one-click (Chrome + server)'
            $ico = Join-Path $ToolboxRoot 'assets\AI-HTML-Toolbox.ico'
            if (Test-Path -LiteralPath $ico) { $sc.IconLocation = "$ico,0" }
            $sc.Save()
        }
        $steps.Add([ordered]@{ step = 'desktop_shortcut'; ok = $true })
        Write-Setup " [OK] Desktop shortcut" 'Green'
    } catch {
        $steps.Add([ordered]@{ step = 'desktop_shortcut'; ok = $false; error = $_.Exception.Message })
        Write-Setup " [i] Desktop shortcut skipped: $($_.Exception.Message)" 'Yellow'
    }
}

# --- 4) Validate + marker ---
Write-Setup ""
Write-Setup " [4/4] Validate and write setup marker"
# Same-process call - nested powershell -File drops -AsObject returns
$statusScript = Join-Path $PSScriptRoot 'Get-FAFOSetupStatus.ps1'
$status = & $statusScript -ToolboxRoot $ToolboxRoot -AsObject

$criticalOk = $false
if ($status -and $status.readyToLaunch) {
    $criticalOk = $true
} else {
    $venvPy = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
    $criticalOk = (Test-Path -LiteralPath $venvPy) -and
                  (Test-Path -LiteralPath (Join-Path $ToolboxRoot 'Toolbox Launcher.html')) -and
                  (-not $failed)
}

# Always log the run so first-run UI can distinguish never-run vs failed
if (-not (Test-Path -LiteralPath $setupDir)) {
    New-Item -ItemType Directory -Path $setupDir -Force | Out-Null
}
$lastRunOk = $false
$lastRunComplete = $false
$lastRunAt = (Get-Date).ToString('o')

function ConvertTo-PlainJson([object]$Obj, [int]$Depth = 8) {
    # Force round-trip through JSON so nested OrderedDictionary/PSCustomObject serialize cleanly
    $raw = $Obj | ConvertTo-Json -Depth $Depth -Compress:$false
    return $raw
}

if (-not $failed -and $criticalOk) {
    try {
        if (-not (Test-Path -LiteralPath $setupDir)) {
            New-Item -ItemType Directory -Path $setupDir -Force | Out-Null
        }
        $chromePath = $null
        if ($status -and $status.chromePath) { $chromePath = [string]$status.chromePath }

        # Plain step list (avoid List[object] quirks in ConvertTo-Json)
        $stepPlain = @()
        foreach ($s in $steps) {
            $stepPlain += [pscustomobject]@{
                step    = [string]$s.step
                ok      = [bool]$s.ok
                skipped = [bool]($s.skipped)
                error   = $(if ($s.PSObject.Properties['error']) { [string]$s.error } else { $null })
            }
        }

        $marker = [pscustomobject]@{
            version     = 1
            complete    = $true
            completedAt = (Get-Date).ToString('o')
            toolboxRoot = [string]$ToolboxRoot
            hostname    = [string]$env:COMPUTERNAME
            username    = [string]$env:USERNAME
            chromePath  = $chromePath
            steps       = $stepPlain
            endpoint    = 'http://127.0.0.87:18765'
        }
        $json = ConvertTo-PlainJson $marker
        [System.IO.File]::WriteAllText($markerPath, $json, [System.Text.UTF8Encoding]::new($false))
        $steps.Add([ordered]@{ step = 'marker'; ok = $true; path = $markerPath })
        $lastRunOk = $true
        $lastRunComplete = $true
        Write-Setup " [OK] Setup marker written" 'Green'
        Write-Setup "      $markerPath" 'DarkGray'
    } catch {
        $failed = $true
        $steps.Add([ordered]@{ step = 'marker'; ok = $false; error = $_.Exception.Message })
        Write-Setup " [FAIL] Marker: $($_.Exception.Message)" 'Red'
    }
} else {
    $steps.Add([ordered]@{ step = 'marker'; ok = $false; error = 'Critical checks failed; marker not written' })
    Write-Setup " [FAIL] Setup not complete - marker not written" 'Red'
}

try {
    $stepPlain2 = @()
    foreach ($s in $steps) {
        $stepPlain2 += [pscustomobject]@{
            step    = [string]$s.step
            ok      = [bool]$s.ok
            skipped = [bool]($s.skipped)
        }
    }
    $lrObj = [pscustomobject]@{
        version     = 1
        ok          = [bool]$lastRunOk
        complete    = [bool]$lastRunComplete
        ranAt       = [string]$lastRunAt
        toolboxRoot = [string]$ToolboxRoot
        hostname    = [string]$env:COMPUTERNAME
        failed      = [bool]$failed
        criticalOk  = [bool]$criticalOk
        steps       = $stepPlain2
    }
    $lrJson = ConvertTo-PlainJson $lrObj
    [System.IO.File]::WriteAllText($lastRunPath, $lrJson, [System.Text.UTF8Encoding]::new($false))
    Write-Setup " [OK] Last-run log: $lastRunPath" 'DarkGray'
} catch {
    Write-Setup " [i] Could not write last-run log: $($_.Exception.Message)" 'DarkGray'
}

$final = & $statusScript -ToolboxRoot $ToolboxRoot -AsObject
if ($final -is [System.Array]) { $final = $final | Select-Object -First 1 }

$isComplete = $false
$isReady = $false
if ($final) {
    $isComplete = [bool]$final.complete
    $isReady = [bool]$final.readyToLaunch
}

Write-Setup ""
if ($isComplete) {
    Write-Setup " Setup COMPLETE. One-click launch is ready." 'Green'
} elseif ($isReady) {
    Write-Setup " Critical pieces OK - re-run if first-run UI still appears." 'Yellow'
} else {
    Write-Setup " Setup INCOMPLETE. Missing:" 'Red'
    if ($final -and $final.missing) {
        foreach ($m in @($final.missing)) { Write-Setup "   - $m" 'Yellow' }
    }
}
Write-Setup ""
Write-Setup " Launch:  double-click Launch-AI-HTML-Toolbox.bat" 'Cyan'
Write-Setup " Server:  http://127.0.0.87:18765"
Write-Setup ""

if ($AsObject) {
    return [pscustomobject]@{
        ok            = $isComplete
        complete      = $isComplete
        readyToLaunch = $isReady
        toolboxRoot   = $ToolboxRoot
        markerPath    = $markerPath
        lastRunPath   = $lastRunPath
    }
}
if ($Quiet) {
    [pscustomobject]@{
        ok            = $isComplete
        complete      = $isComplete
        readyToLaunch = $isReady
        toolboxRoot   = $ToolboxRoot
        markerPath    = $markerPath
    } | ConvertTo-Json -Compress
}
if ($isComplete) { exit 0 } else { exit 2 }
