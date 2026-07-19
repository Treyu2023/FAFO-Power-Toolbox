# Creates Desktop + optional Start Menu shortcuts with a custom .ico
# Best way to get a non-generic icon for an HTML toolbox on Windows.
param(
  [string]$IconPath = "",
  [switch]$StartMenu
)

$ErrorActionPreference = 'Stop'
$ToolboxRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LauncherHtml = Join-Path $ToolboxRoot 'Toolbox Launcher.html'
$LaunchBat = Join-Path $ToolboxRoot 'Launch-AI-HTML-Toolbox.bat'
$DefaultIco = Join-Path $ToolboxRoot 'assets\AI-HTML-Toolbox.ico'
$IconLibrary = 'C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO'

if (-not (Test-Path $LauncherHtml)) { throw "Missing: $LauncherHtml" }
if (-not (Test-Path $LaunchBat)) { throw "Missing: $LaunchBat" }

if (-not $IconPath) { $IconPath = $DefaultIco }
if (-not (Test-Path $IconPath)) {
  Write-Host "Icon not found: $IconPath"
  Write-Host "Using default or pick from: $IconLibrary"
  if (Test-Path $DefaultIco) { $IconPath = $DefaultIco }
}

$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'AI HTML Toolbox.lnk'

$w = New-Object -ComObject WScript.Shell
$sc = $w.CreateShortcut($shortcutPath)
# Target the .bat so we can open Edge/Chrome in --app mode; icon comes from the .lnk
$sc.TargetPath = $LaunchBat
$sc.WorkingDirectory = $ToolboxRoot
$sc.WindowStyle = 7  # minimized console flash
$sc.Description = 'AI HTML Toolbox — local tools launcher'
if (Test-Path $IconPath) {
  $sc.IconLocation = "$IconPath,0"
}
$sc.Save()

Write-Host "Created: $shortcutPath"
Write-Host "Icon:    $IconPath"

if ($StartMenu) {
  $sm = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
  $smPath = Join-Path $sm 'AI HTML Toolbox.lnk'
  Copy-Item -Force $shortcutPath $smPath
  Write-Host "Created: $smPath"
}

Write-Host ""
Write-Host "Done. Pin 'AI HTML Toolbox' from the Desktop to the taskbar for a custom icon."
Write-Host "To use a different icon from your library:"
Write-Host "  .\Install-Desktop-Shortcut.ps1 -IconPath `"$IconLibrary\YourIcon.ico`""
