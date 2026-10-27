# Start the standalone FAFO Auto Tech repo and open it in a Chrome app window.
# The shop that runs is C:\_Git\repos\html\FAFO-Auto-Tech (npm run dev, port 8080).
# If that server is already up, this only opens the window.
$ErrorActionPreference = 'Stop'

$Repo = 'C:\_Git\repos\html\FAFO-Auto-Tech'
$Url = 'http://127.0.0.1:8080/?shop=1'
$Chrome = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'

function Test-PortOpen {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $wait = $client.BeginConnect('127.0.0.1', 8080, $null, $null)
        $ok = $wait.AsyncWaitHandle.WaitOne(400)
        if (-not $ok) { return $false }
        $client.EndConnect($wait)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Open-AutoTechWindow {
    if (Test-Path -LiteralPath $Chrome) {
        Start-Process -FilePath $Chrome -ArgumentList "--app=$Url"
        return
    }
    Start-Process $Url
}

if (-not (Test-Path -LiteralPath (Join-Path $Repo 'package.json'))) {
    Write-Host "FAFO Auto Tech is not on this PC yet. Cloning it."
    $parent = Split-Path -Parent $Repo
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    & git clone https://github.com/Treyu2023/FAFO-Auto-Tech.git $Repo
    if ($LASTEXITCODE -ne 0) { throw "Could not clone FAFO-Auto-Tech." }
}

Set-Location -LiteralPath $Repo

if (-not (Test-Path -LiteralPath (Join-Path $Repo 'node_modules'))) {
    Write-Host "First launch: installing FAFO Auto Tech."
    & npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
}

if (Test-PortOpen) {
    Open-AutoTechWindow
    exit 0
}

$waiter = Join-Path $PSScriptRoot 'Open-FAFO-Auto-Tech-When-Ready.ps1'
Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', $waiter
) -WindowStyle Hidden

Write-Host "FAFO Auto Tech stays up while this window is open. Close the window to stop it."
# Call vite through node.exe. `npm run dev` spawns the vite.cmd shim, which fails on Windows.
& node .\scripts\with-app-env.mjs node .\node_modules\vite\bin\vite.js dev --host 0.0.0.0 --port 8080
exit $LASTEXITCODE
