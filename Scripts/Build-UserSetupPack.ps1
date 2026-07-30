# Build-UserSetupPack.ps1
# Compose a personal BAT folder from setup/install-catalog.json + module choices.
# Does NOT move originals — writes wrapper .bat files that call them.
#
# Usage:
#   .\Scripts\Build-UserSetupPack.ps1 -Modules core,server_s1,verifone -PackName "FieldTech"
#   .\Scripts\Build-UserSetupPack.ps1 -Workflow tech-full -PackName "MyTech"

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [string[]]$Modules = @(),
    [string]$Workflow = '',
    [string]$PackName = 'My-FAFO-Setup',
    [string]$OutRoot = '',
    [switch]$AsObject
)

$ErrorActionPreference = 'Stop'
if (-not $ToolboxRoot) { $ToolboxRoot = Split-Path -Parent $PSScriptRoot }
$ToolboxRoot = (Resolve-Path -LiteralPath $ToolboxRoot).Path

$catalogPath = Join-Path $ToolboxRoot 'setup\install-catalog.json'
if (-not (Test-Path -LiteralPath $catalogPath)) {
    throw "Missing catalog: $catalogPath"
}
$catalog = Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8 | ConvertFrom-Json

$selected = [System.Collections.ArrayList]@()
function Add-Mod([string]$Id) {
    if (-not $Id) { return }
    if ($script:selected -notcontains $Id) { [void]$script:selected.Add($Id) }
}
if ($Workflow) {
    $wf = $catalog.workflows | Where-Object { $_.id -eq $Workflow } | Select-Object -First 1
    if (-not $wf) { throw "Unknown workflow: $Workflow" }
    foreach ($m in @($wf.modules)) { Add-Mod ([string]$m) }
}
# Accept -Modules core,server_s1  OR  -Modules "core,server_s1" (single string from cmd/API)
foreach ($m in @($Modules)) {
    foreach ($part in ([string]$m) -split '[,;]') {
        Add-Mod ($part.Trim())
    }
}
# Always include core first
if ($selected -notcontains 'core') { [void]$selected.Insert(0, 'core') }

# Expand dependsOn
$modById = @{}
foreach ($m in $catalog.modules) { $modById[[string]$m.id] = $m }
$changed = $true
while ($changed) {
    $changed = $false
    foreach ($id in @($selected)) {
        $mod = $modById[$id]
        if (-not $mod) { continue }
        foreach ($dep in @($mod.dependsOn)) {
            $d = [string]$dep
            if ($d -and ($selected -notcontains $d)) {
                [void]$selected.Insert(0, $d)
                $changed = $true
            }
        }
    }
}

# Validate modules exist
foreach ($id in @($selected)) {
    if (-not $modById.ContainsKey($id)) { throw "Unknown module: $id" }
}

$safeName = ($PackName -replace '[^\w\- ]', '').Trim()
if (-not $safeName) { $safeName = 'My-FAFO-Setup' }
if (-not $OutRoot) {
    $OutRoot = Join-Path $env:LOCALAPPDATA "FAFO\user-setup-packs\$safeName"
}
New-Item -ItemType Directory -Path $OutRoot -Force | Out-Null

function Write-BatUtf8([string]$Path, [string]$Content) {
    # CMD-friendly CRLF, no BOM issues for ASCII wrappers
    $Content = $Content -replace "`r?`n", "`r`n"
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

$rootBat = $ToolboxRoot
if (-not $rootBat.EndsWith('\')) { $rootBat += '\' }

# Collect scripts by role
$installScripts = New-Object System.Collections.Generic.List[object]
$startScripts = New-Object System.Collections.Generic.List[object]
$stopScripts = New-Object System.Collections.Generic.List[object]
$launchScripts = New-Object System.Collections.Generic.List[object]
$allRows = New-Object System.Collections.Generic.List[object]

foreach ($id in $selected) {
    $mod = $modById[$id]
    foreach ($sc in @($mod.scripts)) {
        $row = [pscustomobject]@{
            module = $id
            path   = [string]$sc.path
            role   = [string]$sc.role
            note   = [string]$sc.note
            exists = Test-Path -LiteralPath (Join-Path $ToolboxRoot $sc.path)
        }
        [void]$allRows.Add($row)
        switch ($row.role) {
            'install' { [void]$installScripts.Add($row) }
            'start'   { [void]$startScripts.Add($row) }
            'stop'    { [void]$stopScripts.Add($row) }
            'launch'  { [void]$launchScripts.Add($row) }
        }
    }
}

# --- 00 Install ---
$installBody = @"
@echo off
setlocal EnableExtensions
title FAFO user pack - Install ($safeName)
cd /d "$ToolboxRoot"

echo.
echo  ========================================
echo   FAFO personalized install pack
echo   Pack: $safeName
echo   Root: $ToolboxRoot
echo  ========================================
echo  Modules: $($selected -join ', ')
echo.

"@

# Prefer single full installer once if core selected
$installBody += @"
if exist "Install FAFO Toolbox.bat" (
  echo  [1/2] Running core installer...
  call "Install FAFO Toolbox.bat"
  set "EC=!ERRORLEVEL!"
) else if exist "Scripts\Install-FAFOToolbox.ps1" (
  echo  [1/2] Running Install-FAFOToolbox.ps1...
  powershell -NoProfile -ExecutionPolicy Bypass -File "Scripts\Install-FAFOToolbox.ps1" -ToolboxRoot "%CD%"
  set "EC=!ERRORLEVEL!"
) else (
  echo  ERROR: Core installer not found.
  pause
  exit /b 1
)

echo.
echo  [2/2] Module-specific notes written to this pack folder.
echo  Servers are NOT auto-started unless you run 01-Start-My-Servers.bat
echo.
pause
exit /b 0
"@
# Fix delayed expansion for ERRORLEVEL - simplify install bat
$installBody = @"
@echo off
title FAFO user pack - Install ($safeName)
cd /d "$ToolboxRoot"

echo.
echo  ========================================
echo   FAFO personalized install pack
echo   Pack: $safeName
echo  ========================================
echo  Modules: $($selected -join ', ')
echo.
echo  Running core installer only once (not every tool's bat)...
echo.

if exist "Install FAFO Toolbox.bat" (
  call "Install FAFO Toolbox.bat"
  set "EC=%ERRORLEVEL%"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "Scripts\Install-FAFOToolbox.ps1" -ToolboxRoot "%CD%"
  set "EC=%ERRORLEVEL%"
)

echo.
echo  Done. Next: 01-Start-My-Servers.bat  then  02-Open-Launcher.bat
echo  Pack folder: $OutRoot
echo.
pause
exit /b %EC%
"@
Write-BatUtf8 (Join-Path $OutRoot '00-Install-Selected.bat') $installBody

# --- 01 Start servers (only selected) ---
$wantS1 = $selected -contains 'server_s1'
$wantS2 = $selected -contains 'server_s2'
$startBody = @"
@echo off
title FAFO pack - Start my servers ($safeName)
cd /d "$ToolboxRoot"

echo.
echo  Starting only the servers you selected...
echo.

"@
if ($wantS1 -and $wantS2) {
    $startBody += @"
if exist "Start Servers.bat" (
  call "Start Servers.bat"
) else if exist "Scripts\Start-FAFOServers.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%CD%" -Quiet
)
"@
} elseif ($wantS1) {
    $startBody += @"
if exist "1-Start-HTML-Toolbox-Server.bat" (
  call "1-Start-HTML-Toolbox-Server.bat"
) else if exist "Scripts\Start-FAFOServers.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "Scripts\Start-FAFOServers.ps1" -ToolboxRoot "%CD%" -ToolboxOnly -Quiet
)
"@
} elseif ($wantS2) {
    $startBody += @"
if exist "2-Start-FAFO-Local-Media-Tagger.bat" (
  call "2-Start-FAFO-Local-Media-Tagger.bat"
)
"@
} else {
    $startBody += "echo  No servers selected for this pack.`r`n"
}
$startBody += @"

echo.
echo  Done.
pause
"@
Write-BatUtf8 (Join-Path $OutRoot '01-Start-My-Servers.bat') $startBody

# --- Stop ---
$stopBody = @"
@echo off
title FAFO pack - Stop servers
cd /d "$ToolboxRoot"
if exist "Stop-ALL-Servers.bat" (
  call "Stop-ALL-Servers.bat"
) else (
  echo Stop script not found.
  pause
)
"@
Write-BatUtf8 (Join-Path $OutRoot '02-Stop-My-Servers.bat') $stopBody

# --- Open launcher ---
$launchBody = @"
@echo off
title FAFO pack - Open launcher
cd /d "$ToolboxRoot"
if exist "Launch-AI-HTML-Toolbox.bat" (
  call "Launch-AI-HTML-Toolbox.bat"
) else if exist "Toolbox Launcher.html" (
  start "" "Toolbox Launcher.html"
) else (
  echo Launcher not found.
  pause
)
"@
Write-BatUtf8 (Join-Path $OutRoot '03-Open-Launcher.bat') $launchBody

# --- Optional: open key apps as individual wrappers ---
$appsDir = Join-Path $OutRoot 'Open-Apps'
New-Item -ItemType Directory -Path $appsDir -Force | Out-Null
$appN = 0
foreach ($id in $selected) {
    $mod = $modById[$id]
    foreach ($sc in @($mod.scripts)) {
        if ($sc.role -ne 'app' -and $sc.role -ne 'launch') { continue }
        $rel = [string]$sc.path
        if ($rel -notmatch '\.(html|bat|hta)$') { continue }
        $appN++
        $leaf = [IO.Path]::GetFileNameWithoutExtension($rel) -replace '[^\w\- ]', ''
        if (-not $leaf) { $leaf = "App$appN" }
        $batName = ('{0:D2}-{1}.bat' -f $appN, $leaf)
        $full = Join-Path $ToolboxRoot $rel
        $isBat = $rel -match '\.bat$'
        if ($isBat) {
            $content = @"
@echo off
cd /d "$ToolboxRoot"
call "$rel"
"@
        } else {
            # Prefer same-origin via S1 when possible
            $urlPath = ($rel -replace '\\', '/')
            $content = @"
@echo off
cd /d "$ToolboxRoot"
:: Prefer toolbox server URL when online; fallback to file
start "" "http://127.0.0.87:18765/toolbox/$urlPath"
"@
        }
        Write-BatUtf8 (Join-Path $appsDir $batName) $content
    }
}

# --- README + selected.json ---
$readme = @"
FAFO personalized setup pack: $safeName
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm')
Toolbox root: $ToolboxRoot

Modules:
$(($selected | ForEach-Object { "  - $_" }) -join "`r`n")

How to use (in order):
  1) 00-Install-Selected.bat     one-time core install
  2) 01-Start-My-Servers.bat     only servers you selected
  3) 03-Open-Launcher.bat        open FAFO toolbox
  4) Open-Apps\                  optional shortcuts to selected tools

Stop servers:
  02-Stop-My-Servers.bat

Original scripts were NOT moved. This folder only contains wrappers.
Catalog: setup\install-catalog.json
Docs:    docs\Install-Catalog.md
"@
[System.IO.File]::WriteAllText((Join-Path $OutRoot 'README.txt'), ($readme -replace "`n", "`r`n"), [System.Text.UTF8Encoding]::new($false))

$scriptMaps = @()
foreach ($r in $allRows) {
    $scriptMaps += @{
        module = [string]$r.module
        path   = [string]$r.path
        role   = [string]$r.role
        note   = [string]$r.note
        exists = [bool]$r.exists
    }
}
$modList = @($selected | ForEach-Object { [string]$_ })
$manifest = @{
    schema       = 'FAFO.UserSetupPack/1'
    packName     = $safeName
    generatedAt  = (Get-Date).ToString('o')
    toolboxRoot  = $ToolboxRoot
    modules      = $modList
    workflow     = [string]$Workflow
    outRoot      = $OutRoot
    scripts      = $scriptMaps
}
($manifest | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $OutRoot 'selected.json') -Encoding UTF8

$result = @{
    ok          = $true
    packName    = $safeName
    outRoot     = $OutRoot
    modules     = $modList
    scriptCount = $scriptMaps.Count
    message     = "Pack written to $OutRoot"
}
# Always emit one JSON line for API / tooling
$json = ($result | ConvertTo-Json -Depth 6 -Compress)
Write-Output $json
if (-not $AsObject) {
    Write-Host ""
    Write-Host "  Pack ready: $OutRoot" -ForegroundColor Green
    Write-Host "  Run 00-Install-Selected.bat first." -ForegroundColor Cyan
}
if ($AsObject) { return [pscustomobject]$result }
