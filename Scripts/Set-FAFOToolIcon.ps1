# Set-FAFOToolIcon.ps1
# Copy tool/app icons into assets/tool-icons and update the shared manifest.
# Shared icons ship with the repo so anyone who pulls GitHub gets the same defaults.
#
# Modes:
#   Single icon:   -ToolId image-compare -SourcePath "C:\path\to\icon.ico"
#   Publish/sync:  -PublishShared          (rebuild manifest from assets + import selections/library)
#   List tools:    -ListTools
#   Open folder:   -OpenFolder

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,

    # Tool id from the launcher (e.g. image-compare, media-library) or "app" for main shortcut
    [string]$ToolId,

    # Source image: .png .gif .jpg .jpeg .webp .ico .svg .bmp
    [string]$SourcePath,

    [switch]$AsAppIcon,

    # Rebuild shared icons: scan assets/tool-icons, apply icon-sources.json selections,
    # optionally import name-matched files from your local icon library.
    [switch]$PublishShared,

    # With -PublishShared, also scan library folders for tool-id / alias matches
    [switch]$ScanLibrary,

    # Extra library root(s) for this run (appended to icon-sources libraryRoots)
    [string[]]$LibraryRoot = @(),

    [switch]$ListTools,
    [switch]$OpenFolder,

    # After setting app icon / publish, refresh Desktop + Start Menu shortcut
    [switch]$RefreshShortcut
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

$iconsDir = Join-Path $ToolboxRoot 'assets\tool-icons'
$manifestPath = Join-Path $iconsDir 'manifest.json'
$manifestJsPath = Join-Path $iconsDir 'manifest.js'
$sourcesPath = Join-Path $iconsDir 'icon-sources.json'
$legacyAppIco = Join-Path $ToolboxRoot 'assets\AI-HTML-Toolbox.ico'
$allowed = @('.png', '.gif', '.jpg', '.jpeg', '.webp', '.ico', '.svg', '.bmp')

$knownTools = @(
    'app',
    'ip-profile-switcher', 'pc-reports-log-viewer', 'log-viewer',
    'media-library', 'file-organizer', 'vsr-pipeline',
    'video-compare', 'image-compare', 'video-wall', 'image-cropper',
    'loan-calc', 'ghost-device-cleaner', 'lan-task-manager', 'malware-defender',
    'health-dashboard', 'startup-manager', 'disk-analyzer', 'hosts-blocker',
    'media-converter', 'duplicate-finder', 'git-manager', 'bloodmoon-survivor',
    'all'
)

# Friendly basenames that map to launcher tool ids (for auto-import from library)
$defaultAliases = @{
    'app'                  = @('app', 'ninja-toolbox-launcher', 'ai-html-toolbox', 'toolbox-launcher')
    'image-compare'        = @('image-compare', 'image-comparator', 'image-comparitor')
    'video-compare'        = @('video-compare', 'video-comparator', 'video-comparitor')
    'media-library'        = @('media-library', 'media-library-manager')
    'file-organizer'       = @('file-organizer')
    'vsr-pipeline'         = @('vsr-pipeline', 'vsr')
    'video-wall'           = @('video-wall', 'fafo-video-wall')
    'image-cropper'        = @('image-cropper', 'image-converter-cropper')
    'loan-calc'            = @('loan-calc', 'loan-calculator', 'amortization')
    'ghost-device-cleaner'  = @('ghost-device-cleaner', 'ghost-device', 'ghost-devices')
    'lan-task-manager'     = @('lan-task-manager', 'lan-manager', 'task-manager')
    'malware-defender'     = @('malware-defender', 'malware')
    'health-dashboard'     = @('health-dashboard', 'system-health')
    'startup-manager'      = @('startup-manager', 'startup-service-manager')
    'disk-analyzer'        = @('disk-analyzer', 'disk-space-analyzer')
    'hosts-blocker'        = @('hosts-blocker', 'hosts-dns-blocker')
    'media-converter'      = @('media-converter', 'batch-media-converter')
    'duplicate-finder'     = @('duplicate-finder', 'duplicate-file-manager')
    'git-manager'          = @('git-manager', 'git-repository-manager')
    'bloodmoon-survivor'   = @('bloodmoon-survivor', 'bloodmoon')
    'ip-profile-switcher'  = @('ip-profile-switcher', 'ip-profile')
    'pc-reports-log-viewer'= @('pc-reports-log-viewer', 'pc-reports', 'log-viewer-reports')
    'log-viewer'           = @('log-viewer')
    'all'                  = @('all')
}

$defaultLibraryRoots = @(
    (Join-Path $env:USERPROFILE 'OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO'),
    'C:\Users\rkey2\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO'
)

function Normalize-ToolId {
    param([string]$Id)
    $t = ($Id.Trim().ToLowerInvariant() -replace '[^\w\-]+', '-').Trim('-')
    return $t
}

function Normalize-BaseName {
    param([string]$Name)
    return (($Name -replace '\.svg$', '') -replace '[^\w]+', '-').ToLowerInvariant().Trim('-')
}

function Expand-PathLoose {
    param([string]$PathText)
    if ([string]::IsNullOrWhiteSpace($PathText)) { return $null }
    $expanded = [Environment]::ExpandEnvironmentVariables($PathText.Trim())
    try {
        return [IO.Path]::GetFullPath($expanded)
    }
    catch {
        return $expanded
    }
}

function Get-DefaultSourcesConfig {
    return [ordered]@{
        version          = 1
        note             = 'Maps tool ids to source icon files. Used by Set-FAFOToolIcon -PublishShared. Relative paths are under libraryRoots.'
        libraryRoots     = @(
            '%USERPROFILE%\OneDrive\Desktop\AI LOCAL Proj Bin\Completed ICO'
        )
        preferSubfolders = @(
            'HTML Code Tools Specific Icons'
        )
        aliases          = $defaultAliases
        # Absolute or library-relative paths for icons you already picked
        selections       = [ordered]@{}
    }
}

function Read-SourcesConfig {
    $cfg = Get-DefaultSourcesConfig
    if (-not (Test-Path -LiteralPath $sourcesPath)) {
        return $cfg
    }
    try {
        $raw = Get-Content -LiteralPath $sourcesPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Write-Warning "Could not parse icon-sources.json: $_"
        return $cfg
    }
    if ($raw.libraryRoots) {
        $cfg.libraryRoots = @($raw.libraryRoots | ForEach-Object { [string]$_ })
    }
    if ($raw.preferSubfolders) {
        $cfg.preferSubfolders = @($raw.preferSubfolders | ForEach-Object { [string]$_ })
    }
    if ($raw.aliases) {
        $raw.aliases.PSObject.Properties | ForEach-Object {
            $cfg.aliases[$_.Name] = @($_.Value | ForEach-Object { [string]$_ })
        }
    }
    if ($raw.selections) {
        $raw.selections.PSObject.Properties | ForEach-Object {
            if ($_.Value) {
                $cfg.selections[$_.Name] = [string]$_.Value
            }
        }
    }
    if ($raw.note) { $cfg.note = [string]$raw.note }
    return $cfg
}

function Write-SourcesConfig {
    param($Config)
    New-Item -ItemType Directory -Force -Path $iconsDir | Out-Null
    # Convert ordered hashtables / nested hashtables to JSON-friendly objects
    $export = [ordered]@{
        version          = 1
        note             = [string]$Config.note
        libraryRoots     = @($Config.libraryRoots)
        preferSubfolders = @($Config.preferSubfolders)
        aliases          = [ordered]@{}
        selections       = [ordered]@{}
    }
    foreach ($k in @($Config.aliases.Keys | Sort-Object)) {
        $export.aliases[$k] = @($Config.aliases[$k])
    }
    foreach ($k in @($Config.selections.Keys | Sort-Object)) {
        if ($Config.selections[$k]) {
            $export.selections[$k] = [string]$Config.selections[$k]
        }
    }
    $json = $export | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($sourcesPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
}

function Get-LibraryRoots {
    param($Config, [string[]]$Extra)
    $roots = New-Object System.Collections.Generic.List[string]
    foreach ($r in @($Config.libraryRoots) + @($Extra) + $defaultLibraryRoots) {
        $full = Expand-PathLoose $r
        if ($full -and (Test-Path -LiteralPath $full) -and -not ($roots -contains $full)) {
            $roots.Add($full) | Out-Null
        }
    }
    return @($roots)
}

function Resolve-SelectionPath {
    param(
        [string]$Selection,
        [string[]]$LibraryRoots
    )
    $sel = Expand-PathLoose $Selection
    if ($sel -and (Test-Path -LiteralPath $sel)) { return $sel }
    foreach ($root in $LibraryRoots) {
        $candidate = Join-Path $root ($Selection -replace '/', '\')
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

function Get-SelectionRelative {
    param(
        [string]$AbsolutePath,
        [string[]]$LibraryRoots
    )
    $full = Expand-PathLoose $AbsolutePath
    if (-not $full) { return $AbsolutePath }
    foreach ($root in $LibraryRoots) {
        $rootFull = Expand-PathLoose $root
        if (-not $rootFull) { continue }
        if ($full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
            $rel = $full.Substring($rootFull.Length).TrimStart('\', '/')
            return ($rel -replace '\\', '/')
        }
    }
    return $full
}

function Read-Manifest {
    $manifest = @{
        version   = 1
        updatedAt = $null
        note      = 'Shared tool icons for all users. Personal overrides live in browser IndexedDB.'
        app       = $null
        icons     = @{}
    }
    if (Test-Path -LiteralPath $manifestPath) {
        try {
            $existing = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($existing.app) { $manifest.app = [string]$existing.app }
            if ($existing.icons) {
                $existing.icons.PSObject.Properties | ForEach-Object {
                    $manifest.icons[$_.Name] = [string]$_.Value
                }
            }
            if ($existing.note) { $manifest.note = [string]$existing.note }
            if ($existing.version) { $manifest.version = [int]$existing.version }
        }
        catch { }
    }
    return $manifest
}

function Write-Manifest {
    param($Manifest)
    New-Item -ItemType Directory -Force -Path $iconsDir | Out-Null
    $Manifest.version = 1
    $Manifest.updatedAt = (Get-Date).ToUniversalTime().ToString('o')
    if (-not $Manifest.note) {
        $Manifest.note = 'Shared tool icons for all users. Personal overrides live in browser IndexedDB.'
    }
    # Stable key order for nicer diffs
    $iconsOrdered = [ordered]@{}
    foreach ($k in @($Manifest.icons.Keys | Sort-Object)) {
        $iconsOrdered[$k] = $Manifest.icons[$k]
    }
    $export = [ordered]@{
        version   = $Manifest.version
        updatedAt = $Manifest.updatedAt
        note      = $Manifest.note
        app       = $Manifest.app
        icons     = $iconsOrdered
    }
    $json = $export | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($manifestPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    $js = "/* Auto-generated - shared tool icons. Do not edit by hand. */`nwindow.AITOOLBOX_ICON_MANIFEST = $json;`n"
    [System.IO.File]::WriteAllText($manifestJsPath, $js, [System.Text.UTF8Encoding]::new($false))
}

function Set-SharedIconFile {
    param(
        [string]$ToolId,
        [string]$SourcePath,
        [switch]$AsAppIcon,
        [switch]$SkipSourcesUpdate,
        $SourcesConfig
    )

    $tid = Normalize-ToolId $ToolId
    if (-not $tid) { throw 'ToolId required' }
    if (-not (Test-Path -LiteralPath $SourcePath)) {
        throw "Source not found: $SourcePath"
    }

    $ext = [IO.Path]::GetExtension($SourcePath).ToLowerInvariant()
    if ($ext -eq '.jpeg') { $ext = '.jpg' }
    # Handle accidental double extension like .svg.svg
    if ($ext -eq '.svg' -and $SourcePath -match '\.svg\.svg$') { $ext = '.svg' }
    if ($ext -notin $allowed) {
        throw "Unsupported extension '$ext'. Use: $($allowed -join ' ')"
    }

    New-Item -ItemType Directory -Force -Path $iconsDir | Out-Null

    Get-ChildItem -LiteralPath $iconsDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.BaseName -ieq $tid -and $allowed -contains $_.Extension.ToLowerInvariant() } |
        ForEach-Object {
            if ($PSCmdlet.ShouldProcess($_.FullName, 'Remove previous icon')) {
                Remove-Item -LiteralPath $_.FullName -Force
            }
        }

    $destName = "$tid$ext"
    $dest = Join-Path $iconsDir $destName
    if ($PSCmdlet.ShouldProcess($dest, "Copy icon from $SourcePath")) {
        Copy-Item -LiteralPath $SourcePath -Destination $dest -Force
    }

    $manifest = Read-Manifest
    if ($tid -eq 'app' -or $AsAppIcon) {
        $manifest.app = $destName
    }
    if ($tid -ne 'app') {
        $manifest.icons[$tid] = $destName
    }
    Write-Manifest -Manifest $manifest

    if ($tid -eq 'app' -and $ext -eq '.ico') {
        if ($PSCmdlet.ShouldProcess($legacyAppIco, 'Update legacy app icon copy')) {
            Copy-Item -LiteralPath $dest -Destination $legacyAppIco -Force
        }
    }

    if (-not $SkipSourcesUpdate -and $SourcesConfig) {
        $roots = Get-LibraryRoots -Config $SourcesConfig -Extra $LibraryRoot
        $SourcesConfig.selections[$tid] = Get-SelectionRelative -AbsolutePath $SourcePath -LibraryRoots $roots
        Write-SourcesConfig -Config $SourcesConfig
    }

    return [pscustomobject]@{
        ToolId   = $tid
        File     = $destName
        Path     = $dest
        Source   = $SourcePath
    }
}

function Rebuild-ManifestFromAssets {
    $manifest = Read-Manifest
    $found = @{}
    Get-ChildItem -LiteralPath $iconsDir -File -ErrorAction SilentlyContinue |
        Where-Object {
            $allowed -contains $_.Extension.ToLowerInvariant() -and
            $_.Name -notmatch '^(README|manifest|icon-sources)'
        } |
        ForEach-Object {
            $tid = Normalize-ToolId $_.BaseName
            # Prefer .ico when multiple extensions exist for same id
            if (-not $found.ContainsKey($tid)) {
                $found[$tid] = $_
            }
            else {
                $cur = $found[$tid]
                $prefer = @('.ico', '.png', '.webp', '.gif', '.jpg', '.svg', '.bmp')
                $newRank = [array]::IndexOf($prefer, $_.Extension.ToLowerInvariant())
                $curRank = [array]::IndexOf($prefer, $cur.Extension.ToLowerInvariant())
                if ($newRank -ge 0 -and ($curRank -lt 0 -or $newRank -lt $curRank)) {
                    $found[$tid] = $_
                }
            }
        }

    foreach ($tid in $found.Keys) {
        $name = $found[$tid].Name
        if ($tid -eq 'app') {
            $manifest.app = $name
        }
        else {
            $manifest.icons[$tid] = $name
        }
    }

    # Drop manifest entries whose files are gone
    $toRemove = @($manifest.icons.Keys | Where-Object {
            $f = Join-Path $iconsDir $manifest.icons[$_]
            -not (Test-Path -LiteralPath $f)
        })
    foreach ($k in $toRemove) { $manifest.icons.Remove($k) }
    if ($manifest.app) {
        $appPath = Join-Path $iconsDir $manifest.app
        if (-not (Test-Path -LiteralPath $appPath)) { $manifest.app = $null }
    }

    Write-Manifest -Manifest $manifest
    return $manifest
}

function Find-LibraryMatch {
    param(
        [string]$ToolId,
        $Config,
        [string[]]$LibraryRoots
    )

    $aliases = @($ToolId)
    if ($Config.aliases -and $null -ne $Config.aliases[$ToolId]) {
        $aliases = @($Config.aliases[$ToolId]) + $aliases
    }
    $aliasNorm = @($aliases | ForEach-Object { Normalize-BaseName $_ } | Select-Object -Unique)

    $searchDirs = New-Object System.Collections.Generic.List[string]
    foreach ($root in $LibraryRoots) {
        foreach ($sub in @($Config.preferSubfolders)) {
            $p = Join-Path $root $sub
            if (Test-Path -LiteralPath $p) { $searchDirs.Add($p) | Out-Null }
        }
        $searchDirs.Add($root) | Out-Null
    }

    $candidates = @()
    foreach ($dir in $searchDirs) {
        Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue |
            Where-Object { $allowed -contains $_.Extension.ToLowerInvariant() } |
            ForEach-Object {
                $bn = Normalize-BaseName $_.BaseName
                if ($aliasNorm -contains $bn) {
                    $candidates += $_
                }
            }
    }

    if (-not $candidates) { return $null }

    # Prefer: preferSubfolders path, then .ico, then shortest name
    $preferExt = @('.ico', '.png', '.webp', '.gif', '.jpg', '.svg', '.bmp')
    $sorted = $candidates | Sort-Object @(
        @{ Expression = {
                $inPrefer = $false
                foreach ($root in $LibraryRoots) {
                    foreach ($sub in @($Config.preferSubfolders)) {
                        $pref = Join-Path $root $sub
                        if ($_.FullName.StartsWith($pref, [StringComparison]::OrdinalIgnoreCase)) {
                            $inPrefer = $true
                        }
                    }
                }
                if ($inPrefer) { 0 } else { 1 }
            } }
        @{ Expression = {
                $i = [array]::IndexOf($preferExt, $_.Extension.ToLowerInvariant())
                if ($i -lt 0) { 99 } else { $i }
            } }
        @{ Expression = { $_.Name.Length } }
    )
    return $sorted | Select-Object -First 1
}

function Invoke-PublishShared {
    param($Config)

    New-Item -ItemType Directory -Force -Path $iconsDir | Out-Null
    $roots = Get-LibraryRoots -Config $Config -Extra $LibraryRoot
    $results = New-Object System.Collections.Generic.List[object]

    Write-Host "Publishing shared tool icons → $iconsDir" -ForegroundColor Cyan
    if ($roots.Count) {
        Write-Host "Library roots:" -ForegroundColor DarkGray
        $roots | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }
    else {
        Write-Host "No icon library roots found (optional). Using assets/tool-icons only." -ForegroundColor Yellow
    }

    # 1) Explicit selections from icon-sources.json
    foreach ($tid in @($Config.selections.Keys | Sort-Object)) {
        $sel = [string]$Config.selections[$tid]
        if (-not $sel) { continue }
        $src = Resolve-SelectionPath -Selection $sel -LibraryRoots $roots
        if (-not $src) {
            Write-Warning "Selection for '$tid' not found: $sel"
            continue
        }
        try {
            $r = Set-SharedIconFile -ToolId $tid -SourcePath $src -SkipSourcesUpdate -SourcesConfig $Config
            $results.Add([pscustomobject]@{ Action = 'selection'; ToolId = $r.ToolId; File = $r.File; Source = $r.Source }) | Out-Null
            Write-Host "  [selection] $tid ← $src" -ForegroundColor Green
        }
        catch {
            Write-Warning "Failed selection $tid : $_"
        }
    }

    # 2) Optional library scan by tool id / aliases
    if ($ScanLibrary -and $roots.Count) {
        $ids = @($knownTools) + @($Config.aliases.Keys) | Select-Object -Unique
        foreach ($tid in $ids) {
            if ($Config.selections -and $Config.selections[$tid]) {
                continue  # already handled
            }
            $existing = Get-ChildItem -LiteralPath $iconsDir -File -ErrorAction SilentlyContinue |
                Where-Object { (Normalize-ToolId $_.BaseName) -eq $tid -and $allowed -contains $_.Extension.ToLowerInvariant() }
            if ($existing) { continue }

            $match = Find-LibraryMatch -ToolId $tid -Config $Config -LibraryRoots $roots
            if (-not $match) { continue }
            try {
                $r = Set-SharedIconFile -ToolId $tid -SourcePath $match.FullName -SourcesConfig $Config
                $results.Add([pscustomobject]@{ Action = 'library'; ToolId = $r.ToolId; File = $r.File; Source = $r.Source }) | Out-Null
                Write-Host "  [library]   $tid ← $($match.FullName)" -ForegroundColor Green
            }
            catch {
                Write-Warning "Failed library import $tid : $_"
            }
        }
    }

    # 3) Rebuild manifest from whatever is now in assets/tool-icons
    $manifest = Rebuild-ManifestFromAssets

    # Ensure sources file exists for next time (with any new selections from library)
    Write-SourcesConfig -Config $Config

    Write-Host ""
    Write-Host "Shared manifest ready for git:" -ForegroundColor Green
    Write-Host "  app   : $($manifest.app)"
    $iconCount = @($manifest.icons.Keys).Count
    Write-Host "  tools : $iconCount icon(s)"
    foreach ($k in ($manifest.icons.Keys | Sort-Object)) {
        Write-Host "    $k → $($manifest.icons[$k])"
    }
    Write-Host ""
    Write-Host "Commit these so others get the icons on pull:" -ForegroundColor Cyan
    Write-Host "  assets/tool-icons/"
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor DarkGray
    Write-Host "  git add assets/tool-icons"
    Write-Host "  git commit -m `"Share selected tool icons`""
    Write-Host "  git push"

    return [pscustomobject]@{
        Manifest = $manifest
        Results  = $results
        IconsDir = $iconsDir
    }
}

# --- entry points ---

if ($ListTools) {
    Write-Host "Known tool ids:" -ForegroundColor Cyan
    $knownTools | ForEach-Object { Write-Host "  $_" }
    if (Test-Path $manifestPath) {
        Write-Host "`nCurrent shared manifest:" -ForegroundColor Cyan
        Get-Content $manifestPath -Raw
    }
    if (Test-Path $sourcesPath) {
        Write-Host "`nIcon source selections (icon-sources.json):" -ForegroundColor Cyan
        Get-Content $sourcesPath -Raw
    }
    return
}

if ($OpenFolder) {
    New-Item -ItemType Directory -Force -Path $iconsDir | Out-Null
    Start-Process explorer.exe -ArgumentList $iconsDir
    return
}

$sourcesConfig = Read-SourcesConfig

if ($PublishShared) {
    $pub = Invoke-PublishShared -Config $sourcesConfig
    if ($RefreshShortcut) {
        $install = Join-Path $ToolboxRoot 'Install-Desktop-Shortcut.ps1'
        if (Test-Path $install) {
            & $install -StartMenu
        }
    }
    return $pub
}

# Single-icon mode
if (-not $ToolId) {
    Write-Host "Known tools: $($knownTools -join ', ')" -ForegroundColor DarkGray
    Write-Host "Tip: run with -PublishShared to auto-copy already-selected icons into assets/tool-icons" -ForegroundColor DarkGray
    $ToolId = Read-Host "ToolId (or 'app')"
}
if (-not $SourcePath) {
    $SourcePath = Read-Host "Full path to icon image/GIF/ICO"
}

$result = Set-SharedIconFile -ToolId $ToolId -SourcePath $SourcePath -AsAppIcon:$AsAppIcon -SourcesConfig $sourcesConfig

Write-Host ""
Write-Host "Shared icon set:" -ForegroundColor Green
Write-Host "  ToolId : $($result.ToolId)"
Write-Host "  File   : $($result.Path)"
Write-Host "  Selection recorded in assets/tool-icons/icon-sources.json"
Write-Host "  Manifest updated. Commit assets/tool-icons to share with all users."
Write-Host ""
Write-Host "Bulk re-publish later:"
Write-Host "  .\Scripts\Set-FAFOToolIcon.ps1 -PublishShared"
Write-Host "  .\Scripts\Set-FAFOToolIcon.ps1 -PublishShared -ScanLibrary"
Write-Host ""
Write-Host "Launcher priority: personal (browser) > shared (this file) > emoji"

if ($RefreshShortcut -or $result.ToolId -eq 'app' -or $AsAppIcon) {
    if ($RefreshShortcut) {
        $install = Join-Path $ToolboxRoot 'Install-Desktop-Shortcut.ps1'
        if (Test-Path $install) {
            Write-Host ""
            & $install -StartMenu
        }
    }
    else {
        Write-Host "Optional Desktop shortcut refresh:"
        Write-Host "  .\Install-Desktop-Shortcut.ps1 -IconPath `"$($result.Path)`""
    }
}
