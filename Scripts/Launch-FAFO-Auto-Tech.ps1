# Start FAFO Auto Mechanic and open it in a Chrome app window.
# The shop that runs is C:\_Git\repos\html\FAFO-Auto-Tech (npm run dev, port 8080).
# A different program already listening on 8080 is not opened.
$ErrorActionPreference = 'Stop'

$Repo = 'C:\_Git\repos\html\FAFO-Auto-Tech'
$Url = 'http://127.0.0.1:8080/?shop=1'
$Marker = 'fafo-auto-tech'
$Chrome = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
$ToolboxRoot = Split-Path -Parent $PSScriptRoot
$Bat = Join-Path $ToolboxRoot 'Launch-FAFO-Auto-Tech.bat'

function Repair-DesktopShortcut {
    $shell = New-Object -ComObject WScript.Shell
    $desktops = @(
        [Environment]::GetFolderPath('Desktop'),
        (Join-Path $env:USERPROFILE 'Desktop'),
        (Join-Path $env:USERPROFILE 'OneDrive\Desktop')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
    $oldNames = @('FAFO Auto Technician.lnk', 'FAFO Auto Tech.lnk', 'Mustang.lnk')
    foreach ($desktop in $desktops) {
        $icon = ''
        foreach ($old in $oldNames) {
            $oldPath = Join-Path $desktop $old
            if (-not (Test-Path -LiteralPath $oldPath)) { continue }
            $prev = $shell.CreateShortcut($oldPath)
            if (-not $icon -and $prev.IconLocation) { $icon = $prev.IconLocation }
            Remove-Item -LiteralPath $oldPath -Force
        }
        $linkPath = Join-Path $desktop 'FAFO Auto Mechanic.lnk'
        $link = $shell.CreateShortcut($linkPath)
        $link.TargetPath = $Bat
        $link.WorkingDirectory = $ToolboxRoot
        $link.WindowStyle = 1
        $link.Description = 'FAFO Auto Mechanic. Replaces the old Mustang page.'
        if ($icon) { $link.IconLocation = $icon }
        $link.Save()
    }
}

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

function Test-Standalone {
    try {
        $body = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:8080/fafo-app.txt').Content.Trim()
        return $body -eq $Marker
    } catch {
        return $false
    }
}

function Open-AutoTechWindow {
    if (Test-Path -LiteralPath $Chrome) {
        Start-Process -FilePath $Chrome -ArgumentList "--app=$Url"
        return
    }
    Start-Process $Url
}

Repair-DesktopShortcut

if (-not (Test-Path -LiteralPath (Join-Path $Repo 'package.json'))) {
    Write-Host "FAFO Auto Mechanic is not on this PC yet. Cloning the standalone repo."
    $parent = Split-Path -Parent $Repo
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    & git clone https://github.com/Treyu2023/FAFO-Auto-Tech.git $Repo
    if ($LASTEXITCODE -ne 0) { throw "Could not clone FAFO-Auto-Tech." }
}

Set-Location -LiteralPath $Repo

$dirty = git status --porcelain
if (-not $dirty) {
    & git pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw "Could not update FAFO-Auto-Tech. The desktop shortcut was not opened." }
} else {
    Write-Host "Local edits in FAFO-Auto-Tech were left in place."
}

if (-not (Test-Path -LiteralPath (Join-Path $Repo 'node_modules'))) {
    Write-Host "First launch: installing FAFO Auto Mechanic."
    & npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
}

if (Test-PortOpen) {
    if (-not (Test-Standalone)) {
        throw "Port 8080 is already in use by a different app. Close that app, then launch FAFO Auto Mechanic again."
    }
    Open-AutoTechWindow
    exit 0
}

$waiter = Join-Path $PSScriptRoot 'Open-FAFO-Auto-Tech-When-Ready.ps1'
Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', $waiter
) -WindowStyle Hidden

Write-Host "FAFO Auto Mechanic stays up while this window is open. Close the window to stop it."
& node .\scripts\with-app-env.mjs node .\node_modules\vite\bin\vite.js dev --host 0.0.0.0 --port 8080
exit $LASTEXITCODE
