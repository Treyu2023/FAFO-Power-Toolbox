# Creates Desktop + Start Menu shortcuts so users never hunt install folders.
# Prefers shared assets/tool-icons/app.* then legacy assets/AI-HTML-Toolbox.ico
param(
  [string]$IconPath = "",
  [switch]$StartMenu,
  [switch]$NoStartMenu
)

$ErrorActionPreference = 'Stop'
$ToolboxRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LauncherHtml = Join-Path $ToolboxRoot 'Toolbox Launcher.html'
$LaunchBat = Join-Path $ToolboxRoot 'Launch-AI-HTML-Toolbox.bat'
$StartServersBat = Join-Path $ToolboxRoot 'Start Servers.bat'
$IconsDir = Join-Path $ToolboxRoot 'assets\tool-icons'
$DefaultIco = Join-Path $ToolboxRoot 'assets\AI-HTML-Toolbox.ico'
$wantStartMenu = $true
if ($NoStartMenu) { $wantStartMenu = $false }
if ($StartMenu) { $wantStartMenu = $true }

function Resolve-DefaultIcon {
  $manifestPath = Join-Path $IconsDir 'manifest.json'
  if (Test-Path $manifestPath) {
    try {
      $m = Get-Content $manifestPath -Raw | ConvertFrom-Json
      if ($m.app) {
        $p = Join-Path $IconsDir ([string]$m.app)
        if (Test-Path $p) { return $p }
      }
    } catch {}
  }
  foreach ($name in @('app.ico', 'app.png', 'app.gif', 'app.webp', 'app.jpg')) {
    $p = Join-Path $IconsDir $name
    if (Test-Path $p) { return $p }
  }
  if (Test-Path $DefaultIco) { return $DefaultIco }
  return $null
}

function New-FafoShortcut {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Target,
    [string]$Arguments = '',
    [string]$WorkDir = $ToolboxRoot,
    [string]$Description = '',
    [string]$Icon = $script:LnkIcon
  )
  $dir = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  $w = New-Object -ComObject WScript.Shell
  $sc = $w.CreateShortcut($Path)
  $sc.TargetPath = $Target
  if ($Arguments) { $sc.Arguments = $Arguments }
  $sc.WorkingDirectory = $WorkDir
  $sc.WindowStyle = 7
  $sc.Description = $Description
  if ($Icon -and (Test-Path -LiteralPath $Icon)) {
    $sc.IconLocation = "$Icon,0"
  }
  $sc.Save()
  Write-Host "Created: $Path"
}

if (-not (Test-Path $LauncherHtml)) { throw "Missing: $LauncherHtml" }
if (-not (Test-Path $LaunchBat)) { throw "Missing: $LaunchBat" }
if (-not (Test-Path $StartServersBat)) {
  $StartServersBat = Join-Path $ToolboxRoot 'START SERVER.bat'
}
if (-not (Test-Path $StartServersBat)) { throw "Missing Start Servers.bat" }

if (-not $IconPath) { $IconPath = Resolve-DefaultIcon }
if (-not $IconPath -or -not (Test-Path $IconPath)) {
  Write-Host "Icon not found - using default if present"
  if (Test-Path $DefaultIco) { $IconPath = $DefaultIco }
}

$script:LnkIcon = $IconPath
$ext = if ($IconPath) { [IO.Path]::GetExtension($IconPath).ToLowerInvariant() } else { '' }
if ($ext -and $ext -ne '.ico') {
  $preferIco = @(
    (Join-Path $IconsDir 'app.ico'),
    $DefaultIco
  ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  if ($preferIco) {
    Write-Host "Note: Windows shortcuts prefer .ico - using $preferIco for the .lnk"
    $script:LnkIcon = $preferIco
  }
}

$desktop = [Environment]::GetFolderPath('Desktop')

New-FafoShortcut -Path (Join-Path $desktop 'AI HTML Toolbox.lnk') `
  -Target $LaunchBat `
  -Description 'AI HTML Toolbox - app + background servers'

New-FafoShortcut -Path (Join-Path $desktop 'AI HTML Toolbox - Start Servers.lnk') `
  -Target $StartServersBat `
  -Description 'Relaunch FAFO servers in background + tray'

if ($wantStartMenu) {
  $smDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AI HTML Toolbox'
  New-FafoShortcut -Path (Join-Path $smDir 'AI HTML Toolbox.lnk') `
    -Target $LaunchBat `
    -Description 'AI HTML Toolbox - app + background servers'
  New-FafoShortcut -Path (Join-Path $smDir 'Start Servers.lnk') `
    -Target $StartServersBat `
    -Description 'Relaunch companion servers (hidden) + system tray'
  $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $ps1 = Join-Path $ToolboxRoot 'Scripts\Start-FAFOServers.ps1'
  if (Test-Path -LiteralPath $ps1) {
    New-FafoShortcut -Path (Join-Path $smDir 'Restart Servers.lnk') `
      -Target $ps `
      -Arguments "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`" -ToolboxRoot `"$ToolboxRoot`" -Restart -Quiet" `
      -Description 'Stop + start companions + tray (hidden)'
  }
}

Write-Host ""
Write-Host "Done. Pin AI HTML Toolbox or Start Servers to the taskbar for one-click relaunch."
Write-Host "Servers run hidden (no console). Tray icon: Restart / Open Launcher."
Write-Host "No UAC required for local loopback servers."
Write-Host "Shared tool icons: assets\tool-icons\"
