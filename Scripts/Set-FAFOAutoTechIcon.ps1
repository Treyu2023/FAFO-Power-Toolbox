# Point the FAFO Auto Technician desktop shortcut at an icon you pick.
# The shortcut stays a normal .lnk, so Properties, Change Icon still works.
param(
    [string]$SourcePath = ''
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$ToolboxRoot = Split-Path -Parent $PSScriptRoot
$IconDir = 'C:\Users\rkey2\OneDrive\Custom Icons and Theme\Completed ICO\Custom'
$IconPath = Join-Path $IconDir 'FAFO-Auto-Tech.ico'
$ShortcutName = 'FAFO Auto Technician.lnk'
$Bat = Join-Path $ToolboxRoot 'Launch-FAFO-Auto-Tech.bat'

function Write-PngIco {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][int[]]$Sizes,
        [Parameter(Mandatory)][byte[][]]$Pngs
    )
    $fs = [IO.File]::Open($Path, 'Create')
    $bw = New-Object IO.BinaryWriter $fs
    try {
        $bw.Write([uint16]0)
        $bw.Write([uint16]1)
        $bw.Write([uint16]$Pngs.Count)
        $offset = 6 + (16 * $Pngs.Count)
        for ($i = 0; $i -lt $Pngs.Count; $i++) {
            $side = $Sizes[$i]
            $dim = if ($side -ge 256) { [byte]0 } else { [byte]$side }
            $bw.Write($dim)
            $bw.Write($dim)
            $bw.Write([byte]0)
            $bw.Write([byte]0)
            $bw.Write([uint16]1)
            $bw.Write([uint16]32)
            $bw.Write([uint32]$Pngs[$i].Length)
            $bw.Write([uint32]$offset)
            $offset += $Pngs[$i].Length
        }
        foreach ($png in $Pngs) { $bw.Write($png) }
    } finally {
        $bw.Close()
        $fs.Close()
    }
}

function Save-DrawnIcon {
    param([Parameter(Mandatory)][string]$Path)
    $sizes = @(16, 24, 32, 48, 64, 256)
    $pngs = New-Object System.Collections.Generic.List[byte[]]
    foreach ($side in $sizes) {
        $bmp = New-Object System.Drawing.Bitmap $side, $side
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.SmoothingMode = 'AntiAlias'
        $g.Clear([System.Drawing.Color]::FromArgb(255, 16, 22, 28))
        $paint = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 232, 164, 44))
        $g.FillEllipse($paint, [single]($side * 0.16), [single]($side * 0.30), [single]($side * 0.68), [single]($side * 0.34))
        $ms = New-Object IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $pngs.Add($ms.ToArray())
        $ms.Dispose()
        $paint.Dispose()
        $g.Dispose()
        $bmp.Dispose()
    }
    $dir = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-PngIco -Path $Path -Sizes $sizes -Pngs $pngs.ToArray()
}

function Convert-ImageToIco {
    param(
        [Parameter(Mandatory)][string]$Source,
        [Parameter(Mandatory)][string]$Dest
    )
    $ext = [IO.Path]::GetExtension($Source).ToLowerInvariant()
    $dir = Split-Path -Parent $Dest
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    if ($ext -eq '.ico') {
        Copy-Item -LiteralPath $Source -Destination $Dest -Force
        return
    }
    $img = [System.Drawing.Image]::FromFile((Resolve-Path -LiteralPath $Source))
    try {
        $sizes = @(16, 24, 32, 48, 64, 256)
        $pngs = New-Object System.Collections.Generic.List[byte[]]
        foreach ($side in $sizes) {
            $bmp = New-Object System.Drawing.Bitmap $side, $side
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.InterpolationMode = 'HighQualityBicubic'
            $g.SmoothingMode = 'AntiAlias'
            $g.PixelOffsetMode = 'HighQuality'
            $g.Clear([System.Drawing.Color]::Transparent)
            $g.DrawImage($img, 0, 0, $side, $side)
            $ms = New-Object IO.MemoryStream
            $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
            $pngs.Add($ms.ToArray())
            $ms.Dispose()
            $g.Dispose()
            $bmp.Dispose()
        }
        Write-PngIco -Path $Dest -Sizes $sizes -Pngs $pngs.ToArray()
    } finally {
        $img.Dispose()
    }
}

function Update-ShortcutIcon {
    param([Parameter(Mandatory)][string]$Ico)
    if (-not (Test-Path -LiteralPath $Bat)) { throw "Missing $Bat" }
    $desktop = [Environment]::GetFolderPath('Desktop')
    $linkPath = Join-Path $desktop $ShortcutName
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($linkPath)
    $link.TargetPath = $Bat
    $link.WorkingDirectory = $ToolboxRoot
    $link.WindowStyle = 1
    $link.Description = 'FAFO Auto Technician. Standalone shop. Right-click, Properties, Change Icon, or run Change-FAFO-Auto-Tech-Icon.bat.'
    $link.IconLocation = "$Ico,0"
    $link.Save()
    Write-Host "Shortcut: $linkPath"
    Write-Host "Icon:     $Ico"
}

if ($SourcePath) {
    if (-not (Test-Path -LiteralPath $SourcePath)) { throw "File not found: $SourcePath" }
    Convert-ImageToIco -Source $SourcePath -Dest $IconPath
} elseif (-not (Test-Path -LiteralPath $IconPath)) {
    Save-DrawnIcon -Path $IconPath
}

Update-ShortcutIcon -Ico $IconPath
