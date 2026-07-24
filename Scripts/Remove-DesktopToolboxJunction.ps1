# Remove Desktop "AI HTML TOOLBOX" junction that blocks OneDrive backup.
# Safe: only deletes the junction link, NOT the real repo at C:\_Git\...
# Run from an elevated or normal PowerShell AFTER closing Grok CLI / editors
# that have the Desktop path open.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\Scripts\Remove-DesktopToolboxJunction.ps1

$ErrorActionPreference = "Stop"
$junction = Join-Path $env:USERPROFILE "OneDrive\Desktop\AI HTML TOOLBOX"
$real = "C:\_Git\HTMLPROJECTS\AI HTML TOOLBOX"
$shortcut = Join-Path $env:USERPROFILE "OneDrive\Desktop\AI HTML TOOLBOX.lnk"

Write-Host "Real repo:  $real"
Write-Host "Junction:   $junction"

if (-not (Test-Path -LiteralPath $real)) {
  throw "Real toolbox not found at $real — aborting (won't remove junction without verified target)."
}

if (-not (Test-Path -LiteralPath $junction)) {
  Write-Host "No junction at Desktop path. Nothing to remove."
} else {
  $item = Get-Item -LiteralPath $junction -Force
  if ($item.LinkType -ne "Junction") {
    throw "Desktop item exists but is not a Junction (LinkType=$($item.LinkType)). Aborting for safety."
  }
  $tgt = ($item.Target | Select-Object -First 1)
  if ($tgt -notmatch "HTMLPROJECTS[\\/]AI HTML TOOLBOX") {
    throw "Junction target unexpected: $tgt — aborting."
  }

  # rmdir on a junction removes the link only
  $p = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "rmdir", "`"$junction`"") -Wait -PassThru -NoNewWindow
  if (Test-Path -LiteralPath $junction) {
    Write-Host ""
    Write-Host "Still locked or access denied. Try:" -ForegroundColor Yellow
    Write-Host "  1. Close Grok CLI, VS Code, Cursor, terminals opened on the Desktop path"
    Write-Host "  2. Pause OneDrive briefly (tray icon)"
    Write-Host "  3. Re-run this script"
    Write-Host "  4. Or elevated CMD:  rmdir `"$junction`""
    exit 1
  }
  Write-Host "Junction removed." -ForegroundColor Green
}

if (-not (Test-Path -LiteralPath $real)) {
  throw "Safety check failed: real path missing after rmdir"
}

if (-not (Test-Path -LiteralPath $shortcut)) {
  $wsh = New-Object -ComObject WScript.Shell
  $sc = $wsh.CreateShortcut($shortcut)
  $sc.TargetPath = $real
  $sc.WorkingDirectory = $real
  $sc.Description = "FAFO / AI HTML Toolbox (real path outside OneDrive)"
  $sc.Save()
  Write-Host "Created shortcut: $shortcut" -ForegroundColor Green
} else {
  Write-Host "Shortcut already exists: $shortcut"
}

Write-Host ""
Write-Host "Done. Open the toolbox via the Desktop shortcut or:"
Write-Host "  $real"
Write-Host "OneDrive Desktop backup should no longer see a junction named AI HTML TOOLBOX."
Write-Host "Keep the real git repo on C:\_Git (outside OneDrive) — that is intentional."
