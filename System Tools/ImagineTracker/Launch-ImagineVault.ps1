$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$candidates = @(
    (Join-Path $here 'ImagineVault.py'),
    'C:\_Git\repos\html\fafo-chrome-extensions\FAFO Imagine Tracker\companion\ImagineVault.py'
)
$pyFile = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pyFile) { throw 'ImagineVault.py not found' }

function Find-Python {
    $list = @(
        (Join-Path $env:USERPROFILE 'Desktop\FAFO-Power-Toolbox\.venv\Scripts\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe')
    )
    foreach ($c in $list) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}
$py = Find-Python
if (-not $py) { throw 'Python not found' }

$prot = 'HKCU:\Software\Classes\imaginevault'
New-Item -Path $prot -Force | Out-Null
Set-ItemProperty $prot -Name '(default)' -Value 'URL:Imagine Vault'
New-ItemProperty -Path $prot -Name 'URL Protocol' -Value '' -PropertyType String -Force | Out-Null
$cmdKey = Join-Path $prot 'shell\open\command'
New-Item -Path $cmdKey -Force | Out-Null
$vbs = Join-Path $here 'Launch-ImagineVault.vbs'
Set-ItemProperty $cmdKey -Name '(default)' -Value ("wscript.exe //B `"$vbs`"")

try {
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:18767/health' -UseBasicParsing -TimeoutSec 1
    if ($r.StatusCode -eq 200) { exit 0 }
} catch {}

$work = Join-Path $env:LOCALAPPDATA 'FAFO\ImagineTracker'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$runPy = Join-Path $work 'ImagineVault.py'
Copy-Item -Force $pyFile $runPy
Start-Process -FilePath $py -ArgumentList @('-u', $runPy) -WindowStyle Hidden -WorkingDirectory $work
exit 0
