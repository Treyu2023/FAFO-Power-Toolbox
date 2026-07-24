# Remove Desktop "AI HTML TOOLBOX" junction that blocks OneDrive backup.
# Safe: only deletes the junction link, NOT the real repo at C:\_Git\...
# Run from an elevated or normal PowerShell AFTER closing Grok CLI / editors
# that have the Desktop path open.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\Scripts\Remove-DesktopToolboxJunction.ps1

$ErrorActionPreference = "Stop"

$real = "C:\_Git\HTMLPROJECTS\AI HTML TOOLBOX"
$desktop = [Environment]::GetFolderPath("Desktop")
if (-not $desktop) {
  $desktop = Join-Path $env:USERPROFILE "OneDrive\Desktop"
}
$shortcut = Join-Path $desktop "AI HTML Toolbox.lnk"
$launchBat = Join-Path $real "Launch-AI-HTML-Toolbox.bat"

# Possible leftover names (junction / empty folder) that confuse OneDrive
$suspectNames = @(
  "AI HTML TOOLBOX",
  "AI HTML Toolbox",
  "AI_HTML_TOOLBOX"
)

Write-Host "Real repo:  $real"
Write-Host "Desktop:    $desktop"

if (-not (Test-Path -LiteralPath $real)) {
  throw "Real toolbox not found at $real - aborting (will not remove Desktop items without verified target)."
}
if (-not (Test-Path -LiteralPath (Join-Path $real "Toolbox Launcher.html"))) {
  throw "Real toolbox looks incomplete (missing Toolbox Launcher.html) - aborting."
}

$removed = 0
foreach ($name in $suspectNames) {
  $path = Join-Path $desktop $name
  if (-not (Test-Path -LiteralPath $path)) { continue }

  $item = Get-Item -LiteralPath $path -Force
  if (-not $item.PSIsContainer) {
    Write-Host "Skip non-folder: $path"
    continue
  }

  $isJunction = ($item.LinkType -eq "Junction") -or (
    ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
    ($item.LinkType -eq "Junction" -or $null -eq $item.LinkType)
  )

  # True directory junction only (not OneDrive cloud placeholder)
  $isTrueJunction = $false
  if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    try {
      $rp = (fsutil reparsepoint query $path 2>&1 | Out-String)
      if ($rp -match "0xa0000003" -or $item.LinkType -eq "Junction") {
        $isTrueJunction = $true
      }
    } catch {
      if ($item.LinkType -eq "Junction") { $isTrueJunction = $true }
    }
  }

  if ($isTrueJunction -or $item.LinkType -eq "Junction") {
    $tgt = @($item.Target) | Select-Object -First 1
    if ($tgt -and ($tgt -notmatch "HTMLPROJECTS[\\/]AI HTML TOOLBOX") -and ($tgt -notmatch [regex]::Escape($real))) {
      throw "Junction target unexpected for '$name': $tgt - aborting."
    }
    # rmdir on a junction removes the link only
    $null = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "rmdir", "`"$path`"") -Wait -PassThru -NoNewWindow
    if (Test-Path -LiteralPath $path) {
      Write-Host ""
      Write-Host "Still locked or access denied: $path" -ForegroundColor Yellow
      Write-Host "  1. Close Grok CLI, VS Code, Cursor, terminals opened on the Desktop path"
      Write-Host "  2. Pause OneDrive briefly (tray icon)"
      Write-Host "  3. Re-run this script"
      Write-Host "  4. Or elevated CMD:  rmdir `"$path`""
      exit 1
    }
    Write-Host "Junction removed: $path" -ForegroundColor Green
    $removed++
    continue
  }

  # Empty leftover real folder (not a junction) - safe to remove if empty
  $kids = @(Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue)
  if ($kids.Count -eq 0) {
    Remove-Item -LiteralPath $path -Force
    Write-Host "Removed empty leftover folder: $path" -ForegroundColor Green
    $removed++
  } else {
    Write-Host "Left in place (not a junction, not empty): $path ($($kids.Count) items)" -ForegroundColor Yellow
  }
}

if ($removed -eq 0) {
  Write-Host "No Desktop toolbox junction or empty leftover to remove."
}

if (-not (Test-Path -LiteralPath $real)) {
  throw "Safety check failed: real path missing after cleanup"
}

# Ensure a normal .lnk shortcut (never a junction) points at the real toolbox
$targetPath = if (Test-Path -LiteralPath $launchBat) { $launchBat } else { $real }
$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($shortcut)
$sc.TargetPath = $targetPath
$sc.WorkingDirectory = $real
$sc.Description = "FAFO / AI HTML Toolbox (real path outside OneDrive - use this, not a junction)"
$ico = Join-Path $real "assets\AI-HTML-Toolbox.ico"
if (-not (Test-Path $ico)) {
  $ico = Join-Path $real "assets\tool-icons\app.ico"
}
if (Test-Path $ico) {
  $sc.IconLocation = "$ico,0"
}
$sc.Save()
Write-Host "Shortcut ready: $shortcut" -ForegroundColor Green
Write-Host "  Target: $targetPath"

Write-Host ""
Write-Host "Done."
Write-Host "  Real git repo stays at: $real  (outside OneDrive - intentional)"
Write-Host "  Desktop opens via .lnk only - OneDrive can back up the Desktop again."
Write-Host "  Do not recreate a folder junction named AI HTML TOOLBOX on the Desktop."
