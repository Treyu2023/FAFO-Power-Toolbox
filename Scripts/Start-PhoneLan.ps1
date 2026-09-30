# Start-PhoneLan.ps1
# Static HTML share for Phone Launcher (allowlisted files). Not the loopback API.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [int]$Port = 18780,
    [string]$Bind = '0.0.0.0',
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

$pyScript = Join-Path $ToolboxRoot 'server\phone_static.py'
if (-not (Test-Path -LiteralPath $pyScript)) {
    throw "Missing $pyScript"
}

function Get-FafoPython {
    $venv = Join-Path $ToolboxRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venv) {
        try {
            $p = Start-Process -FilePath $venv -ArgumentList @('-c', 'import sys') -Wait -PassThru -WindowStyle Hidden -ErrorAction Stop
            if ($p.ExitCode -eq 0) { return (Resolve-Path -LiteralPath $venv).Path }
        } catch {}
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "No Python. Run INSTALL-PYTHON.bat once."
}

function Test-PortOpen([int]$PortNum) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect('127.0.0.1', $PortNum, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(400)
        if (-not $ok) { $c.Close(); return $false }
        $c.EndConnect($iar) | Out-Null
        $c.Close()
        return $true
    } catch { return $false }
}

function Open-SharePage([int]$PortNum) {
    $url = "http://127.0.0.1:$PortNum/Phone%20Launcher.html?share=1"
    $chrome = @(
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if ($chrome) {
        Start-Process -FilePath $chrome -ArgumentList @($url) | Out-Null
    } else {
        Start-Process $url | Out-Null
    }
}

$python = Get-FafoPython

if (-not (Test-PortOpen -PortNum $Port)) {
    Write-Host "Starting FAFO Phone LAN on ${Bind}:$Port (static HTML only)..."
    $argLine = "-u `"$pyScript`" --bind $Bind --port $Port"
    Start-Process -FilePath $python -ArgumentList $argLine -WorkingDirectory $ToolboxRoot -WindowStyle Normal | Out-Null
    $deadline = (Get-Date).AddSeconds(8)
    while (-not (Test-PortOpen -PortNum $Port) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 200
    }
    if (-not (Test-PortOpen -PortNum $Port)) {
        throw "Phone LAN did not listen on port $Port. Check the Python window."
    }
} else {
    Write-Host "Phone LAN already listening on port $Port."
}

try {
    $info = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/phone-lan.json" -TimeoutSec 3
    Write-Host "Version $($info.version)"
    if ($info.urls) {
        Write-Host "Phone (same Wi-Fi):"
        foreach ($u in $info.urls) { Write-Host "  $u" }
    }
} catch {
    Write-Host "Listening, but phone-lan.json did not answer yet."
}

if (-not $NoBrowser) { Open-SharePage -PortNum $Port }

Write-Host ""
Write-Host "Keep the Python window open while the phone is using it."
Write-Host "API / secrets stay on 127.0.0.87:18765 — this share is HTML only."
Write-Host "Chrome on the phone: Add to Home screen after the page loads."
