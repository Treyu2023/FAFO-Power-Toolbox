#Requires -Version 5.1
<#
.SYNOPSIS
  Choose the local Verifone site-data folder and create the repo MKLINK junction.

.DESCRIPTION
  Site XML backups are LOCAL ONLY (Customer\Site\...). They are never meant for GitHub.

  This script:
    1) Lets you pick (or pass) a folder for site data
    2) Saves it to %LOCALAPPDATA%\FAFO\local-paths.json (shared by all FAFO apps)
    3) Creates VerifoneLibrary\Sites as mklink /J -> that folder
    4) Optionally migrates any old in-repo demo site folders into the new layout

.PARAMETER Path
  Target data root. If omitted, a folder picker is shown.

.PARAMETER SkipMigrate
  Do not move old VerifoneLibrary\{MOC}\{Customer}\{Site} trees into the new root.
#>
[CmdletBinding()]
param(
    [string]$Path,
    [switch]$SkipMigrate,
    [switch]$NoPrompt
)

$ErrorActionPreference = 'Stop'
$shellRoot = $PSScriptRoot
$toolboxRoot = Split-Path -Parent $shellRoot

$toolboxMod = Join-Path $toolboxRoot 'Scripts\Modules\FAFO.Toolbox\FAFO.Toolbox.psd1'
$verifoneMod = Join-Path $toolboxRoot 'Scripts\Modules\FAFO.Verifone\FAFO.Verifone.psd1'

if (-not (Test-Path -LiteralPath $toolboxMod)) {
    throw "FAFO.Toolbox not found: $toolboxMod"
}
Import-Module $toolboxMod -Force
if (Test-Path -LiteralPath $verifoneMod) {
    Import-Module $verifoneMod -Force
}

Write-Host ''
Write-Host 'FAFO Verifone — local site data setup' -ForegroundColor Cyan
Write-Host '  Backups stay on THIS PC (or your chosen drive). Git only gets templates/tools.' -ForegroundColor DarkGray
Write-Host ''

$current = Get-FAFOLocalPaths -ToolboxRoot $toolboxRoot
Write-Host "Current VerifoneSitesRoot: $($current.VerifoneSitesRoot)" -ForegroundColor Gray
Write-Host "Config file: $($current.ConfigPath)" -ForegroundColor DarkGray
Write-Host ''

if (-not $Path) {
    if ($NoPrompt) {
        $Path = $current.VerifoneSitesRoot
        if (-not $Path) { $Path = $current.VerifoneSitesDefault }
    }
    else {
        Write-Host 'Pick the folder that will hold Customer\Site backups.' -ForegroundColor Yellow
        Write-Host 'Examples: D:\FAFO\VerifoneSites  or  leave default under LocalAppData.' -ForegroundColor DarkGray
        $picked = Select-FAFOFolder -Description 'Select Verifone site data folder (local only — not GitHub)' -InitialDirectory $current.VerifoneSitesRoot
        if ($picked) {
            $Path = $picked
        }
        else {
            $useDefault = Read-Host "Use default [$($current.VerifoneSitesDefault)]? [Y/n]"
            if ($useDefault -match '^[nN]') {
                throw 'Cancelled — no data folder selected.'
            }
            $Path = $current.VerifoneSitesDefault
        }
    }
}

$result = Set-FAFOVerifoneSitesRoot -Path $Path -ToolboxRoot $toolboxRoot
Write-Host ''
Write-Host 'Configured:' -ForegroundColor Green
Write-Host "  Data root : $($result.VerifoneSitesRoot)"
if ($result.Link) {
    Write-Host "  Junction  : $($result.Link.LinkPath)"
    Write-Host "           -> $($result.Link.TargetPath)"
}
Write-Host "  Layout    : $($result.Layout)"
Write-Host ''

# Migrate old in-repo site trees (MOC\Customer\Location) if present
if (-not $SkipMigrate) {
    $legacyCandidates = @(
        Get-ChildItem -LiteralPath $shellRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -notin @('Templates', 'Working-PunchLists', 'Sites') -and
                -not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)
            }
    )

    foreach ($top in $legacyCandidates) {
        # Look for site.json under old trees
        $metas = @(Get-ChildItem -LiteralPath $top.FullName -Filter site.json -File -Recurse -ErrorAction SilentlyContinue)
        foreach ($metaFile in $metas) {
            try {
                $m = Get-Content -LiteralPath $metaFile.FullName -Raw | ConvertFrom-Json
                $customer = if ($m.Customer) { $m.Customer } else { 'Unknown-Customer' }
                $site = if ($m.Location) { $m.Location } elseif ($m.Site) { $m.Site } else { 'Unknown-Site' }
                $oldSiteDir = Split-Path -Parent $metaFile.FullName
                $dest = Get-FAFOVerifoneSitePath -Customer $customer -Location $site -LibraryRoot $result.VerifoneSitesRoot

                if ($oldSiteDir -ieq $dest) { continue }
                if ((Test-Path -LiteralPath $dest) -and (Test-Path -LiteralPath (Join-Path $dest 'original'))) {
                    Write-Host "Skip migrate (dest exists): $customer / $site" -ForegroundColor DarkYellow
                    continue
                }

                Write-Host "Migrating: $oldSiteDir" -ForegroundColor Cyan
                Write-Host "       -> $dest" -ForegroundColor Cyan
                $destParent = Split-Path -Parent $dest
                if (-not (Test-Path -LiteralPath $destParent)) {
                    New-Item -Path $destParent -ItemType Directory -Force | Out-Null
                }
                if (Test-Path -LiteralPath $dest) {
                    Remove-Item -LiteralPath $dest -Recurse -Force
                }
                Move-Item -LiteralPath $oldSiteDir -Destination $dest -Force

                # Ensure new subfolders exist
                foreach ($sub in @('original', 'working', 'scripts', 'files', 'punchlists')) {
                    $p = Join-Path $dest $sub
                    if (-not (Test-Path -LiteralPath $p)) {
                        New-Item -Path $p -ItemType Directory -Force | Out-Null
                    }
                }

                # Refresh site.json paths
                if (Get-Command Write-FAFOVerifoneSiteMeta -ErrorAction SilentlyContinue) {
                    # rewrite via public meta if we re-open; simpler: patch SitePath fields
                }
                if (Test-Path -LiteralPath (Join-Path $dest 'site.json')) {
                    $nm = Get-Content -LiteralPath (Join-Path $dest 'site.json') -Raw | ConvertFrom-Json
                    $nm.SitePath = $dest
                    $nm.OriginalPath = Join-Path $dest 'original'
                    $nm.WorkingPath = Join-Path $dest 'working'
                    $nm.ScriptsPath = Join-Path $dest 'scripts'
                    $nm | Add-Member -NotePropertyName FilesPath -NotePropertyValue (Join-Path $dest 'files') -Force
                    $nm | Add-Member -NotePropertyName PunchlistsPath -NotePropertyValue (Join-Path $dest 'punchlists') -Force
                    $nm | Add-Member -NotePropertyName Site -NotePropertyValue $site -Force
                    $nm | ConvertTo-Json -Depth 8 | Out-File -FilePath (Join-Path $dest 'site.json') -Encoding utf8
                }
            }
            catch {
                Write-Warning "Migrate failed for $($metaFile.FullName): $_"
            }
        }

        # Remove empty legacy MOC trees
        try {
            $left = @(Get-ChildItem -LiteralPath $top.FullName -Recurse -Force -ErrorAction SilentlyContinue)
            if ($left.Count -eq 0) {
                Remove-Item -LiteralPath $top.FullName -Force -ErrorAction SilentlyContinue
            }
        }
        catch { }
    }

    if (Get-Command Update-FAFOVerifoneLibraryIndex -ErrorAction SilentlyContinue) {
        Update-FAFOVerifoneLibraryIndex -LibraryRoot $result.VerifoneSitesRoot | Out-Null
    }
}

Write-Host ''
Write-Host 'Next steps:' -ForegroundColor Cyan
Write-Host '  Add-FAFOVerifoneLibraryBackup -Path <folder-with-xml> -Customer "Acme" -Location "Main St 12"'
Write-Host '  Show-FAFOVerifoneLibrary'
Write-Host '  Open-FAFOPath -Which VerifoneSites'
Write-Host ''
Write-Host 'On your laptop after git pull: run this setup once and pick that machine''s data folder.' -ForegroundColor DarkGray
Write-Host ''
