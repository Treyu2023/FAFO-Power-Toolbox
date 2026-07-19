# Set-FAFOToolIcon.ps1
# Copy an image/GIF/ICO into assets/tool-icons and update the shared manifest.
# Shared icons ship with the repo for all users; personal browser overrides still win locally.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,

    # Tool id from the launcher (e.g. image-compare, media-library) or "app" for main shortcut
    [string]$ToolId,

    # Source image: .png .gif .jpg .jpeg .webp .ico .svg .bmp
    [string]$SourcePath,

    [switch]$AsAppIcon,
    [switch]$ListTools,
    [switch]$OpenFolder
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

$iconsDir = Join-Path $ToolboxRoot 'assets\tool-icons'
$manifestPath = Join-Path $iconsDir 'manifest.json'
$allowed = @('.png', '.gif', '.jpg', '.jpeg', '.webp', '.ico', '.svg', '.bmp')

$knownTools = @(
    'app',
    'ip-profile-switcher', 'pc-reports-log-viewer', 'log-viewer',
    'media-library', 'file-organizer', 'vsr-pipeline',
    'video-compare', 'image-compare', 'video-wall', 'image-cropper',
    'loan-calc', 'ghost-device-cleaner', 'lan-task-manager', 'malware-defender',
    'health-dashboard', 'startup-manager', 'disk-analyzer', 'hosts-blocker',
    'media-converter', 'duplicate-finder', 'git-manager', 'bloodmoon-survivor'
)

if ($ListTools) {
    Write-Host "Known tool ids:" -ForegroundColor Cyan
    $knownTools | ForEach-Object { Write-Host "  $_" }
    if (Test-Path $manifestPath) {
        Write-Host "`nCurrent shared manifest:" -ForegroundColor Cyan
        Get-Content $manifestPath -Raw
    }
    return
}

if ($OpenFolder) {
    New-Item -ItemType Directory -Force -Path $iconsDir | Out-Null
    Start-Process explorer.exe -ArgumentList $iconsDir
    return
}

if (-not $ToolId) {
    Write-Host "Known tools: $($knownTools -join ', ')" -ForegroundColor DarkGray
    $ToolId = Read-Host "ToolId (or 'app')"
}
if (-not $SourcePath) {
    $SourcePath = Read-Host "Full path to icon image/GIF/ICO"
}

$ToolId = ($ToolId.Trim().ToLowerInvariant() -replace '[^\w\-]+', '-').Trim('-')
if (-not $ToolId) { throw 'ToolId required' }

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Source not found: $SourcePath"
}

$ext = [IO.Path]::GetExtension($SourcePath).ToLowerInvariant()
if ($ext -eq '.jpeg') { $ext = '.jpg' }
if ($ext -notin $allowed) {
    throw "Unsupported extension '$ext'. Use: $($allowed -join ' ')"
}

New-Item -ItemType Directory -Force -Path $iconsDir | Out-Null

# Remove previous files for this tool id
Get-ChildItem -LiteralPath $iconsDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.BaseName -ieq $ToolId -and $allowed -contains $_.Extension.ToLowerInvariant() } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

$destName = "$ToolId$ext"
$dest = Join-Path $iconsDir $destName
Copy-Item -LiteralPath $SourcePath -Destination $dest -Force

# Update manifest
$manifest = @{
    version   = 1
    updatedAt = (Get-Date).ToUniversalTime().ToString('o')
    note      = 'Shared tool icons for all users. Personal overrides live in browser IndexedDB.'
    app       = $null
    icons     = @{}
}
if (Test-Path -LiteralPath $manifestPath) {
    try {
        $existing = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        if ($existing.app) { $manifest.app = [string]$existing.app }
        if ($existing.icons) {
            $existing.icons.PSObject.Properties | ForEach-Object {
                $manifest.icons[$_.Name] = [string]$_.Value
            }
        }
    }
    catch { }
}

if ($ToolId -eq 'app' -or $AsAppIcon) {
    $manifest.app = $destName
}
if ($ToolId -ne 'app') {
    $manifest.icons[$ToolId] = $destName
}

# Also keep a convenience copy for legacy shortcut script
if ($ToolId -eq 'app' -and $ext -eq '.ico') {
    $legacy = Join-Path $ToolboxRoot 'assets\AI-HTML-Toolbox.ico'
    Copy-Item -LiteralPath $dest -Destination $legacy -Force
}

$json = $manifest | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText($manifestPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
# file:// friendly companion
$jsPath = Join-Path $iconsDir 'manifest.js'
$js = "/* Auto-generated - shared tool icons */`nwindow.AITOOLBOX_ICON_MANIFEST = $json;`n"
[System.IO.File]::WriteAllText($jsPath, $js, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Shared icon set:" -ForegroundColor Green
Write-Host "  ToolId : $ToolId"
Write-Host "  File   : $dest"
Write-Host "  Manifest updated. Commit assets/tool-icons to share with all users."
Write-Host ""
Write-Host "Launcher priority: personal (browser) > shared (this file) > emoji"
Write-Host "Optional Desktop shortcut refresh:"
Write-Host "  .\Install-Desktop-Shortcut.ps1 -IconPath `"$dest`""
