# Start Imagine Vault and keep a supervisor up.
# Always runs the Python files from %LOCALAPPDATA%\FAFO\ImagineTracker so
# venv python launchers cannot split on spaces in "System Tools".
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$work = Join-Path $env:LOCALAPPDATA 'FAFO\ImagineTracker'
New-Item -ItemType Directory -Force -Path $work | Out-Null

function Test-VaultUpEarly {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:18767/health' -UseBasicParsing -TimeoutSec 1
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

$lock = $null
try {
    $lock = [System.IO.File]::Open(
        (Join-Path $work 'launch.lock'),
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
} catch {
    $waitUntil = (Get-Date).AddSeconds(14)
    do {
        if (Test-VaultUpEarly) { exit 0 }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $waitUntil)
    exit 0
}

$srcPy = @(
    (Join-Path $here 'ImagineVault.py'),
    (Join-Path $env:USERPROFILE 'Desktop\FAFO-Power-Toolbox\System Tools\ImagineTracker\ImagineVault.py'),
    'C:\_Git\repos\html\HTML Toolbox AI tools\production\System Tools\ImagineTracker\ImagineVault.py',
    'C:\_Git\repos\html\fafo-chrome-extensions\FAFO Imagine Tracker\companion\ImagineVault.py'
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $srcPy) { throw 'ImagineVault.py not found' }

Copy-Item -LiteralPath $srcPy -Destination (Join-Path $work 'ImagineVault.py') -Force
foreach ($name in @('Launch-ImagineVault.ps1', 'Launch-ImagineVault.vbs', 'Launch-ImagineVault.bat', 'imagine-overlay.js')) {
    $src = Join-Path $here $name
    if (Test-Path -LiteralPath $src) {
        Copy-Item -LiteralPath $src -Destination (Join-Path $work $name) -Force
    }
}

function Find-Python {
    $list = @(
        (Join-Path $env:USERPROFILE 'Desktop\FAFO-Power-Toolbox\.venv\Scripts\pythonw.exe'),
        (Join-Path $env:USERPROFILE 'Desktop\FAFO-Power-Toolbox\.venv\Scripts\python.exe'),
        'C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\pythonw.exe',
        'C:\_Git\repos\html\HTML Toolbox AI tools\production\.venv\Scripts\python.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\pythonw.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\pythonw.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\pythonw.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\pythonw.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
    )
    foreach ($c in $list) { if (Test-Path -LiteralPath $c) { return $c } }
    foreach ($name in @('pythonw', 'python', 'py')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

$py = Find-Python
if (-not $py) { throw 'Python not found. Run FAFO INSTALL-PYTHON.bat' }
$pyw = $py
if ($py -match 'python\.exe$') {
    $alt = $py -replace 'python\.exe$', 'pythonw.exe'
    if (Test-Path -LiteralPath $alt) { $pyw = $alt }
}

$vbs = Join-Path $work 'Launch-ImagineVault.vbs'
$prot = 'HKCU:\Software\Classes\imaginevault'
New-Item -Path $prot -Force | Out-Null
Set-ItemProperty $prot -Name '(default)' -Value 'URL:Imagine Vault'
New-ItemProperty -Path $prot -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
$cmdKey = Join-Path $prot 'shell\open\command'
New-Item -Path $cmdKey -Force | Out-Null
Set-ItemProperty $cmdKey -Name '(default)' -Value ("wscript.exe //B `"$vbs`"")

function Test-VaultUp {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:18767/health' -UseBasicParsing -TimeoutSec 1
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Test-WatchAlive {
    $pidFile = Join-Path $work 'vault-watch.pid'
    if (-not (Test-Path -LiteralPath $pidFile)) { return $false }
    $raw = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $wpid = 0
    [void][int]::TryParse($raw, [ref]$wpid)
    if ($wpid -le 0) { return $false }
    return [bool](Get-Process -Id $wpid -ErrorAction SilentlyContinue)
}

$stop = Join-Path $work 'stop.flag'
if (Test-Path -LiteralPath $stop) { Remove-Item -LiteralPath $stop -Force -ErrorAction SilentlyContinue }

if ((Test-WatchAlive) -and -not (Test-VaultUp)) {
    $pidFile = Join-Path $work 'vault-watch.pid'
    $raw = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $wpid = 0
    [void][int]::TryParse($raw, [ref]$wpid)
    if ($wpid -gt 0) { Stop-Process -Id $wpid -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 400
}

# Supervisor starts the HTTP server. Script name only — never a path with spaces.
if (-not (Test-WatchAlive)) {
    Start-Process -FilePath $pyw -ArgumentList @('-u', 'ImagineVault.py', '--watch') -WorkingDirectory $work -WindowStyle Hidden | Out-Null
}

if (Test-VaultUp) { exit 0 }
$deadline = (Get-Date).AddSeconds(14)
do {
    Start-Sleep -Milliseconds 300
    if (Test-VaultUp) { exit 0 }
} while ((Get-Date) -lt $deadline)
exit 0
