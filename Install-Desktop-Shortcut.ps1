# Creates Desktop + optional Start Menu shortcuts with a custom icon.
# Prefers shared assets/tool-icons/app.* then legacy assets/AI-HTML-Toolbox.ico
# Note: Windows .lnk IconLocation works best with .ico; PNG/GIF still work in the HTML launcher.
param(
  [string]$IconPath = "",
  [switch]$StartMenu
)

$ErrorActionPreference = 'Stop'
$ToolboxRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LauncherHtml = Join-Path $ToolboxRoot 'Toolbox Launcher.html'
$LaunchBat = Join-Path $ToolboxRoot 'Launch-AI-HTML-Toolbox.bat'
$IconsDir = Join-Path $ToolboxRoot 'assets\tool-icons'
$DefaultIco = Join-Path $ToolboxRoot 'assets\AI-HTML-Toolbox.ico'
$IconLibrary = 'C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO'

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

if (-not (Test-Path $LauncherHtml)) { throw "Missing: $LauncherHtml" }
if (-not (Test-Path $LaunchBat)) { throw "Missing: $LaunchBat" }

if (-not $IconPath) { $IconPath = Resolve-DefaultIcon }
if (-not $IconPath -or -not (Test-Path $IconPath)) {
  Write-Host "Icon not found. Using shell default or pick from: $IconLibrary"
  if (Test-Path $DefaultIco) { $IconPath = $DefaultIco }
}

# If a non-ico was chosen for the .lnk, prefer any app.ico / legacy ico for Windows shortcuts
$lnkIcon = $IconPath
$ext = if ($IconPath) { [IO.Path]::GetExtension($IconPath).ToLowerInvariant() } else { '' }
if ($ext -and $ext -ne '.ico') {
  $preferIco = @(
    (Join-Path $IconsDir 'app.ico'),
    $DefaultIco
  ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  if ($preferIco) {
    Write-Host "Note: Windows shortcuts prefer .ico — using $preferIco for the .lnk"
    Write-Host "      HTML launcher will still use your image/GIF from tool-icons."
    $lnkIcon = $preferIco
  } else {
    Write-Host "Warning: .lnk icons work best as .ico. Launcher UI supports PNG/GIF/etc."
  }
}

$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'AI HTML Toolbox.lnk'

$w = New-Object -ComObject WScript.Shell
$sc = $w.CreateShortcut($shortcutPath)
$sc.TargetPath = $LaunchBat
$sc.WorkingDirectory = $ToolboxRoot
$sc.WindowStyle = 7
$sc.Description = 'AI HTML Toolbox - local tools launcher'
if ($lnkIcon -and (Test-Path $lnkIcon)) {
  $sc.IconLocation = "$lnkIcon,0"
}
$sc.Save()

Write-Host "Created: $shortcutPath"
Write-Host "Icon:    $lnkIcon"

if ($StartMenu) {
  $sm = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
  $smPath = Join-Path $sm 'AI HTML Toolbox.lnk'
  Copy-Item -Force $shortcutPath $smPath
  Write-Host "Created: $smPath"
}

Write-Host ""
Write-Host "Done. Pin 'AI HTML Toolbox' from the Desktop to the taskbar for a custom icon."
Write-Host "Shared tool icons: assets\tool-icons\  (Set-FAFOToolIcon.ps1 or Launcher Edit Icons)"
Write-Host "  .\Scripts\Set-FAFOToolIcon.ps1 -ToolId app -SourcePath `"path\to\icon.ico`""
