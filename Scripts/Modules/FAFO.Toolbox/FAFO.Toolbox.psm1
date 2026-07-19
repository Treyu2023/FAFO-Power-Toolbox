# FAFO.Toolbox.psm1
# Paths, logging, safe file ops, health, device profiles, and report helpers
# Version: 1.4.0

#region Paths & configuration

function Get-FAFOToolboxRoot {
    [CmdletBinding()]
    param()

    if ($env:FAFO_TOOLBOX_ROOT -and (Test-Path $env:FAFO_TOOLBOX_ROOT)) {
        return (Resolve-Path $env:FAFO_TOOLBOX_ROOT).Path
    }

    # Module is at Scripts\Modules\FAFO.Toolbox\ -> go up 3 levels to toolbox root
    $candidate = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
    if (Test-Path $candidate) {
        return (Resolve-Path $candidate).Path
    }

    throw 'Unable to resolve FAFO toolbox root. Set $env:FAFO_TOOLBOX_ROOT.'
}

function Set-FAFOToolboxRoot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Path does not exist: $Path"
    }

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $env:FAFO_TOOLBOX_ROOT = $resolved
    Write-FAFOLog -Level Info -Message "FAFO_TOOLBOX_ROOT set to $resolved"
    return $resolved
}

function Get-FAFODeviceId {
    [CmdletBinding()]
    param()

    # Prefer stable machine name; sanitize for filesystem
    $name = $env:COMPUTERNAME
    if ([string]::IsNullOrWhiteSpace($name)) {
        try { $name = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).Name } catch { $name = 'UNKNOWN-PC' }
    }
    ($name -replace '[^\w\.-]+', '-').Trim('-').ToUpperInvariant()
}

function Get-FAFOCommonPaths {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot),
        [string]$DeviceId = (Get-FAFODeviceId)
    )

    # Machine-local root — never put per-PC reports/logs in the git tree or OneDrive sync folder.
    $deviceRoot = Join-Path $env:LOCALAPPDATA ("FAFO\Devices\{0}" -f $DeviceId)
    $viewer = Join-Path $ToolboxRoot 'System Tools\PC Reports and Log Viewer'

    [ordered]@{
        ToolboxRoot     = $ToolboxRoot
        DeviceId        = $DeviceId
        DeviceRoot      = $deviceRoot
        Scripts         = Join-Path $ToolboxRoot 'Scripts'
        Modules         = Join-Path $ToolboxRoot 'Scripts\Modules'
        SecretsModule   = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Secrets'
        ToolboxModule   = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Toolbox'
        # Device-scoped (this PC only)
        Reports         = Join-Path $deviceRoot 'Reports'
        Markdown        = Join-Path $deviceRoot 'Reports\Markdown'
        Raw             = Join-Path $deviceRoot 'Reports\Raw'
        Archive         = Join-Path $deviceRoot 'Reports\Archive'
        PcReports       = Join-Path $deviceRoot 'Reports\PC'
        Logs            = Join-Path $deviceRoot 'Logs'
        Backups         = Join-Path $deviceRoot 'Backups'
        # Repo UI (shared code; generated packs are gitignored)
        PcReportViewer  = $viewer
        CatalogJs       = Join-Path $viewer 'catalog.js'
        LogsDataJs      = Join-Path $viewer 'logs-data.js'
        Server          = Join-Path $ToolboxRoot 'server'
        Shared          = Join-Path $ToolboxRoot 'shared'
        SecretsStore    = Join-Path $env:LOCALAPPDATA 'FAFO\Secrets'
        GrokHome        = Join-Path $env:USERPROFILE '.grok'
        InspectScript   = Join-Path $ToolboxRoot 'Scripts\Inspect-GrokInstall.ps1'
        SessionScript   = Join-Path $ToolboxRoot 'Scripts\Initialize-FAFOSession.ps1'
        DiagScript      = Join-Path $ToolboxRoot 'Scripts\Invoke-FAFOSystemDiagnostics.ps1'
        PackLogsScript  = Join-Path $viewer '_pack_logs.ps1'
        BindConfig      = Join-Path $ToolboxRoot 'shared\aitoolbox-bind.json'
        VersionFile     = Join-Path $ToolboxRoot 'VERSION'
        # Machine-local path registry (all apps read this; never commit)
        LocalPathsConfig = Join-Path $env:LOCALAPPDATA 'FAFO\local-paths.json'
        # Default Verifone site data root if user has not chosen one yet
        VerifoneSitesDefault = Join-Path $env:LOCALAPPDATA 'FAFO\VerifoneSites'
        # Repo shell for Verifone tools (templates/launchers only — backups live elsewhere)
        VerifoneLibraryShell = Join-Path $ToolboxRoot 'VerifoneLibrary'
        # Junction inside repo that points at VerifoneSitesRoot (local-only data)
        VerifoneSitesLink    = Join-Path $ToolboxRoot 'VerifoneLibrary\Sites'
    }
}

function Get-FAFOLocalPathsConfigPath {
    <#
    .SYNOPSIS
      Path to the machine-local FAFO path registry (%LOCALAPPDATA%\FAFO\local-paths.json).
    #>
    [CmdletBinding()]
    param()
    Join-Path $env:LOCALAPPDATA 'FAFO\local-paths.json'
}

function Get-FAFOLocalPaths {
    <#
    .SYNOPSIS
      Read machine-local directory settings shared by all FAFO apps.
    .DESCRIPTION
      Source of truth: %LOCALAPPDATA%\FAFO\local-paths.json (never in git).
      Keys currently used:
        VerifoneSitesRoot  - Customer\Site backup library (XML, punch lists, etc.)
    .NOTES
      Env overrides: FAFO_VERIFONE_SITES_ROOT
    #>
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $cfgPath = $paths.LocalPathsConfig
    $cfg = $null
    if (Test-Path -LiteralPath $cfgPath) {
        try {
            $cfg = Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
        }
        catch {
            $cfg = $null
        }
    }

    $verifoneRoot = $null
    if ($env:FAFO_VERIFONE_SITES_ROOT -and (Test-Path -LiteralPath $env:FAFO_VERIFONE_SITES_ROOT)) {
        $verifoneRoot = (Resolve-Path -LiteralPath $env:FAFO_VERIFONE_SITES_ROOT).Path
    }
    elseif ($cfg -and $cfg.VerifoneSitesRoot -and -not [string]::IsNullOrWhiteSpace([string]$cfg.VerifoneSitesRoot)) {
        $verifoneRoot = [string]$cfg.VerifoneSitesRoot
    }
    else {
        $verifoneRoot = $paths.VerifoneSitesDefault
    }

    [PSCustomObject]@{
        ConfigPath           = $cfgPath
        ConfigExists         = [bool](Test-Path -LiteralPath $cfgPath)
        VerifoneSitesRoot    = $verifoneRoot
        VerifoneSitesDefault = $paths.VerifoneSitesDefault
        VerifoneLibraryShell = $paths.VerifoneLibraryShell
        VerifoneSitesLink    = $paths.VerifoneSitesLink
        ToolboxRoot          = $ToolboxRoot
        DeviceId             = $paths.DeviceId
        Machine              = $env:COMPUTERNAME
        Raw                  = $cfg
    }
}

function Save-FAFOLocalPaths {
    <#
    .SYNOPSIS
      Persist machine-local directory settings for all FAFO apps.
    #>
    [CmdletBinding()]
    param(
        [string]$VerifoneSitesRoot,
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $current = Get-FAFOLocalPaths -ToolboxRoot $ToolboxRoot
    $cfgPath = $current.ConfigPath
    $dir = Split-Path -Parent $cfgPath
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -Path $dir -ItemType Directory -Force | Out-Null
    }

    $existing = @{}
    if ($current.Raw) {
        $current.Raw.PSObject.Properties | ForEach-Object { $existing[$_.Name] = $_.Value }
    }

    if ($PSBoundParameters.ContainsKey('VerifoneSitesRoot') -and $VerifoneSitesRoot) {
        $resolved = $VerifoneSitesRoot
        if (Test-Path -LiteralPath $VerifoneSitesRoot) {
            $resolved = (Resolve-Path -LiteralPath $VerifoneSitesRoot).Path
        }
        $existing['VerifoneSitesRoot'] = $resolved
        $env:FAFO_VERIFONE_SITES_ROOT = $resolved
    }

    $existing['Version'] = 1
    $existing['UpdatedAt'] = (Get-Date).ToString('o')
    $existing['Machine'] = $env:COMPUTERNAME
    $existing['DeviceId'] = $current.DeviceId
    $existing['ToolboxRoot'] = $ToolboxRoot

    $obj = [PSCustomObject]$existing
    $obj | ConvertTo-Json -Depth 6 | Out-File -FilePath $cfgPath -Encoding utf8
    Write-FAFOLog -Level Info -Message "Saved local paths config: $cfgPath" -ToolboxRoot $ToolboxRoot
    return Get-FAFOLocalPaths -ToolboxRoot $ToolboxRoot
}

function Select-FAFOFolder {
    <#
    .SYNOPSIS
      Show a Windows folder picker dialog (or fall back to Read-Host).
    #>
    [CmdletBinding()]
    param(
        [string]$Description = 'Select a folder',
        [string]$InitialDirectory
    )

    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialog.Description = $Description
        $dialog.ShowNewFolderButton = $true
        if ($InitialDirectory -and (Test-Path -LiteralPath $InitialDirectory)) {
            $dialog.SelectedPath = (Resolve-Path -LiteralPath $InitialDirectory).Path
        }
        $result = $dialog.ShowDialog()
        if ($result -eq [System.Windows.Forms.DialogResult]::OK -and $dialog.SelectedPath) {
            return $dialog.SelectedPath
        }
        return $null
    }
    catch {
        Write-Host $Description -ForegroundColor Cyan
        $typed = Read-Host 'Folder path (blank to cancel)'
        if ([string]::IsNullOrWhiteSpace($typed)) { return $null }
        return $typed.Trim().Trim('"')
    }
}

function Initialize-FAFODirectoryJunction {
    <#
    .SYNOPSIS
      Create or refresh a directory junction (MKLINK /J) from LinkPath to TargetPath.
    .DESCRIPTION
      Junctions do not require admin on modern Windows and keep large local data
      out of git while apps still open a stable path inside the repo.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$LinkPath,
        [Parameter(Mandatory)][string]$TargetPath
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        New-Item -Path $TargetPath -ItemType Directory -Force | Out-Null
    }
    $target = (Resolve-Path -LiteralPath $TargetPath).Path

    $linkParent = Split-Path -Parent $LinkPath
    if (-not (Test-Path -LiteralPath $linkParent)) {
        New-Item -Path $linkParent -ItemType Directory -Force | Out-Null
    }

    if (Test-Path -LiteralPath $LinkPath) {
        $item = Get-Item -LiteralPath $LinkPath -Force
        $isLink = [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
        if ($isLink) {
            # Refresh if target differs
            $currentTarget = $null
            try {
                # .NET Target property on DirectoryInfo for junctions (PS 5.1+)
                if ($item.Target) {
                    $currentTarget = @($item.Target)[0]
                }
            }
            catch { }
            if ($currentTarget) {
                try {
                    $cur = (Resolve-Path -LiteralPath $currentTarget -ErrorAction SilentlyContinue).Path
                    if ($cur -and ($cur -ieq $target)) {
                        return [PSCustomObject]@{
                            LinkPath   = $LinkPath
                            TargetPath = $target
                            Created    = $false
                            Refreshed  = $false
                            Ok         = $true
                        }
                    }
                }
                catch { }
            }
            $null = cmd /c "rmdir `"$LinkPath`"" 2>$null
        }
        else {
            # Real folder already there — do not destroy user data
            $kids = @(Get-ChildItem -LiteralPath $LinkPath -Force -ErrorAction SilentlyContinue)
            if ($kids.Count -gt 0) {
                throw "Link path exists as a real non-empty folder (not a junction):`n  $LinkPath`nMove/rename it, then re-run setup."
            }
            Remove-Item -LiteralPath $LinkPath -Force -ErrorAction Stop
        }
    }

    $out = cmd /c "mklink /J `"$LinkPath`" `"$target`"" 2>&1
    $ok = Test-Path -LiteralPath $LinkPath
    if (-not $ok) {
        throw "Failed to create junction:`n  $LinkPath -> $target`n$out"
    }

    [PSCustomObject]@{
        LinkPath   = $LinkPath
        TargetPath = $target
        Created    = $true
        Refreshed  = $true
        Ok         = $true
        Message    = ($out | Out-String).Trim()
    }
}

function Initialize-FAFOPaths {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $local = Get-FAFOLocalPaths -ToolboxRoot $ToolboxRoot
    foreach ($dir in @(
            $paths.DeviceRoot,
            $paths.Markdown,
            $paths.Raw,
            $paths.Archive,
            $paths.PcReports,
            $paths.Logs,
            $paths.Backups,
            $local.VerifoneSitesRoot
        )) {
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {
            New-Item -Path $dir -ItemType Directory -Force | Out-Null
        }
    }

    # Optional convenience junction inside the viewer so file:// HTML can open
    # device-local report files via relative paths (device-local/...).
    $viewerLocal = Join-Path $paths.PcReportViewer 'device-local'
    try {
        if (Test-Path -LiteralPath $viewerLocal) {
            $item = Get-Item -LiteralPath $viewerLocal -Force
            $isLink = ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
            if (-not $isLink) {
                # Do not clobber a real folder with data
            }
            else {
                # Refresh junction target if it points elsewhere
                $null = cmd /c "rmdir `"$viewerLocal`"" 2>$null
                $null = cmd /c "mklink /J `"$viewerLocal`" `"$($paths.DeviceRoot)`"" 2>$null
            }
        }
        else {
            $null = cmd /c "mklink /J `"$viewerLocal`" `"$($paths.DeviceRoot)`"" 2>$null
        }
    }
    catch {
        # Junction is optional (needs permissions); pack still works offline via logs-data.js
    }

    # Best-effort repo junction so apps can use VerifoneLibrary\Sites
    try {
        if (Test-Path -LiteralPath $paths.VerifoneLibraryShell) {
            Initialize-FAFODirectoryJunction -LinkPath $paths.VerifoneSitesLink -TargetPath $local.VerifoneSitesRoot | Out-Null
        }
    }
    catch {
        # Junction is optional; apps can still use VerifoneSitesRoot absolute path
    }

    [PSCustomObject]@{
        ToolboxRoot        = $paths.ToolboxRoot
        DeviceId           = $paths.DeviceId
        DeviceRoot         = $paths.DeviceRoot
        MarkdownDir        = $paths.Markdown
        RawDir             = $paths.Raw
        ArchiveDir         = $paths.Archive
        PcReportsDir       = $paths.PcReports
        LogsDir            = $paths.Logs
        BackupsDir         = $paths.Backups
        ViewerDir          = $paths.PcReportViewer
        VerifoneSitesRoot  = $local.VerifoneSitesRoot
        VerifoneSitesLink  = $paths.VerifoneSitesLink
        LocalPathsConfig   = $paths.LocalPathsConfig
    }
}

function Get-FAFOEnvironment {
    [CmdletBinding()]
    param(
        [string[]]$SecretNames = @('XAI_API_KEY', 'ABUSE_CH_AUTH_KEY')
    )

    $secretPresence = [ordered]@{}
    foreach ($name in $SecretNames) {
        $inEnv = -not [string]::IsNullOrWhiteSpace((Get-Item -Path "env:$name" -ErrorAction SilentlyContinue).Value)
        $onDisk = $false
        if (Get-Command Test-FAFOSecret -ErrorAction SilentlyContinue) {
            $onDisk = [bool](Test-FAFOSecret -Name $name)
        }
        elseif (Test-Path (Join-Path $env:LOCALAPPDATA "FAFO\Secrets\$name.xml")) {
            $onDisk = $true
        }
        $secretPresence[$name] = [PSCustomObject]@{
            InEnvironment = $inEnv
            InDpapiStore  = $onDisk
        }
    }

    [PSCustomObject]@{
        FAFO_TOOLBOX_ROOT = $env:FAFO_TOOLBOX_ROOT
        USERNAME          = $env:USERNAME
        COMPUTERNAME      = $env:COMPUTERNAME
        PSVersion         = $PSVersionTable.PSVersion.ToString()
        Secrets           = $secretPresence
        # Never return secret values
    }
}

#endregion

#region Logging

function Write-FAFOLog {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Message,

        [ValidateSet('Debug', 'Info', 'Warn', 'Error')]
        [string]$Level = 'Info',

        [switch]$NoFile,

        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[{0}] [{1,-5}] {2}" -f $stamp, $Level.ToUpper(), $Message

    $color = switch ($Level) {
        'Debug' { 'DarkGray' }
        'Info'  { 'Cyan' }
        'Warn'  { 'Yellow' }
        'Error' { 'Red' }
    }
    Write-Host $line -ForegroundColor $color

    if (-not $NoFile) {
        try {
            $paths = Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot
            $logFile = Join-Path $paths.LogsDir ("FAFO-{0:yyyyMMdd}.log" -f (Get-Date))
            Add-Content -LiteralPath $logFile -Value $line -Encoding utf8
        }
        catch {
            Write-Host "[$stamp] [WARN ] Failed to write log file: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

#endregion

#region Safe file operations

function Backup-FAFOItem {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory, ValueFromPipeline, ValueFromPipelineByPropertyName)]
        [Alias('FullName', 'Path')]
        [string]$LiteralPath,

        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    process {
        if (-not (Test-Path -LiteralPath $LiteralPath)) {
            throw "Item not found: $LiteralPath"
        }

        $item = Get-Item -LiteralPath $LiteralPath
        $paths = Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $destName = '{0}.{1}.bak' -f $item.Name, $stamp
        $dest = Join-Path $paths.BackupsDir $destName

        if ($item.PSIsContainer) {
            $dest = Join-Path $paths.BackupsDir ("{0}-{1}" -f $item.Name, $stamp)
            Copy-Item -LiteralPath $item.FullName -Destination $dest -Recurse -Force
        }
        else {
            Copy-Item -LiteralPath $item.FullName -Destination $dest -Force
        }

        Write-FAFOLog -Level Info -Message "Backup created: $dest" -ToolboxRoot $ToolboxRoot

        [PSCustomObject]@{
            Source      = $item.FullName
            BackupPath  = $dest
            Timestamp   = $stamp
            IsContainer = [bool]$item.PSIsContainer
        }
    }
}

function Move-FAFOItem {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Destination,

        [switch]$Force,
        [switch]$NoBackup,
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Source not found: $Path"
    }

    $destExists = Test-Path -LiteralPath $Destination
    if ($destExists -and -not $Force) {
        throw "Destination exists (use -Force to overwrite): $Destination"
    }

    if (-not $NoBackup) {
        Backup-FAFOItem -LiteralPath $Path -ToolboxRoot $ToolboxRoot | Out-Null
    }

    if ($destExists -and $Force) {
        if (-not $NoBackup) {
            Backup-FAFOItem -LiteralPath $Destination -ToolboxRoot $ToolboxRoot | Out-Null
        }
        if ($PSCmdlet.ShouldProcess($Destination, 'Remove existing destination')) {
            Remove-Item -LiteralPath $Destination -Recurse -Force
        }
    }

    if ($PSCmdlet.ShouldProcess($Path, "Move to $Destination")) {
        $destParent = Split-Path -Parent $Destination
        if ($destParent -and -not (Test-Path -LiteralPath $destParent)) {
            New-Item -Path $destParent -ItemType Directory -Force | Out-Null
        }
        Move-Item -LiteralPath $Path -Destination $Destination -Force
        Write-FAFOLog -Level Info -Message "Moved: $Path -> $Destination" -ToolboxRoot $ToolboxRoot
    }

    [PSCustomObject]@{
        Source      = $Path
        Destination = $Destination
        Forced      = [bool]$Force
    }
}

function Copy-FAFOItem {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path,

        [Parameter(Mandatory)]
        [string]$Destination,

        [switch]$Force,
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Source not found: $Path"
    }

    if ((Test-Path -LiteralPath $Destination) -and -not $Force) {
        throw "Destination exists (use -Force to overwrite): $Destination"
    }

    $destParent = Split-Path -Parent $Destination
    if ($destParent -and -not (Test-Path -LiteralPath $destParent)) {
        New-Item -Path $destParent -ItemType Directory -Force | Out-Null
    }

    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        Copy-Item -LiteralPath $Path -Destination $Destination -Recurse -Force:$Force
    }
    else {
        Copy-Item -LiteralPath $Path -Destination $Destination -Force:$Force
    }

    Write-FAFOLog -Level Info -Message "Copied: $Path -> $Destination" -ToolboxRoot $ToolboxRoot

    [PSCustomObject]@{
        Source      = $Path
        Destination = $Destination
    }
}

#endregion

#region Diagnostics & health

function Get-FAFOStatus {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot),
        [string[]]$SecretNames = @('XAI_API_KEY', 'ABUSE_CH_AUTH_KEY')
    )

    $secretsLoaded = [System.Collections.Generic.List[string]]::new()
    foreach ($name in $SecretNames) {
        $present = $false
        if (Get-Command Test-FAFOSecret -ErrorAction SilentlyContinue) {
            $present = [bool](Test-FAFOSecret -Name $name)
        }
        elseif (Test-Path (Join-Path $env:LOCALAPPDATA "FAFO\Secrets\$name.xml")) {
            $present = $true
        }
        if ($present) { $secretsLoaded.Add($name) | Out-Null }
    }

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $reportDirsExist = (Test-Path $paths.Markdown) -and (Test-Path $paths.Raw)
    $grokOnPath = $null -ne (Get-Command grok -ErrorAction SilentlyContinue)
    $pythonOnPath = $null -ne (Get-Command python -ErrorAction SilentlyContinue)
    $secretsModulePresent = Test-Path (Join-Path $paths.SecretsModule 'FAFO.Secrets.psd1')
    $toolboxModulePresent = Test-Path (Join-Path $paths.ToolboxModule 'FAFO.Toolbox.psd1')

    $version = $null
    if (Test-Path -LiteralPath $paths.VersionFile) {
        $version = (Get-Content -LiteralPath $paths.VersionFile -Raw).Trim()
    }

    [PSCustomObject]@{
        ToolboxRoot          = $ToolboxRoot
        Version              = $version
        SecretsLoaded        = @($secretsLoaded)
        GrokOnPath           = $grokOnPath
        PythonOnPath         = $pythonOnPath
        ReportDirsExist      = $reportDirsExist
        SecretsModulePresent = $secretsModulePresent
        ToolboxModulePresent = $toolboxModulePresent
    }
}

function Test-FAFOHealth {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot),
        [string[]]$SecretNames = @('XAI_API_KEY', 'ABUSE_CH_AUTH_KEY')
    )

    $checks = [System.Collections.Generic.List[object]]::new()
    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $status = Get-FAFOStatus -ToolboxRoot $ToolboxRoot -SecretNames $SecretNames

    $null = $checks.Add([PSCustomObject]@{ Name = 'ToolboxRoot'; Ok = (Test-Path $ToolboxRoot); Detail = $ToolboxRoot })
    $null = $checks.Add([PSCustomObject]@{ Name = 'ReportDirs'; Ok = $status.ReportDirsExist; Detail = "$($paths.Markdown) ; $($paths.Raw)" })
    $null = $checks.Add([PSCustomObject]@{ Name = 'SecretsModule'; Ok = $status.SecretsModulePresent; Detail = $paths.SecretsModule })
    $null = $checks.Add([PSCustomObject]@{ Name = 'ToolboxModule'; Ok = $status.ToolboxModulePresent; Detail = $paths.ToolboxModule })
    $null = $checks.Add([PSCustomObject]@{
            Name   = 'GrokOnPath'
            Ok     = $status.GrokOnPath
            Detail = $(if ($status.GrokOnPath) { (Get-Command grok).Source } else { 'grok not found' })
        })
    $null = $checks.Add([PSCustomObject]@{
            Name   = 'PythonOnPath'
            Ok     = $status.PythonOnPath
            Detail = $(if ($status.PythonOnPath) { (Get-Command python).Source } else { 'python not found (optional)' })
        })

    foreach ($name in $SecretNames) {
        $present = $status.SecretsLoaded -contains $name
        $null = $checks.Add([PSCustomObject]@{
                Name   = "Secret:$name"
                Ok     = $present
                Detail = $(if ($present) { 'present in DPAPI store' } else { 'missing' })
            })
    }

    $bindOk = Test-Path -LiteralPath $paths.BindConfig
    $null = $checks.Add([PSCustomObject]@{ Name = 'BindConfig'; Ok = $bindOk; Detail = $paths.BindConfig })

    $serverPy = Join-Path $paths.Server 'aitoolbox_server.py'
    $null = $checks.Add([PSCustomObject]@{ Name = 'ServerEntry'; Ok = (Test-Path -LiteralPath $serverPy); Detail = $serverPy })

    # Critical = everything except Python (optional for pure PowerShell work)
    $criticalFailed = @($checks | Where-Object {
        -not $_.Ok -and $_.Name -ne 'PythonOnPath'
    })

    $overall = $criticalFailed.Count -eq 0

    [PSCustomObject]@{
        OverallOk = $overall
        Failed    = @($criticalFailed | ForEach-Object { $_.Name })
        Checks    = @($checks)
        Status    = $status
        CheckedAt = Get-Date
    }
}

function Write-FAFOStatusReport {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot),
        [string[]]$SecretNames = @('XAI_API_KEY', 'ABUSE_CH_AUTH_KEY'),
        [string]$Name = 'FAFO-Status',
        [switch]$IncludeHealth
    )

    $status = Get-FAFOStatus -ToolboxRoot $ToolboxRoot -SecretNames $SecretNames
    $health = $null
    if ($IncludeHealth) {
        $health = Test-FAFOHealth -ToolboxRoot $ToolboxRoot -SecretNames $SecretNames
    }

    $secretsText = if ($status.SecretsLoaded.Count) {
        ($status.SecretsLoaded -join ', ')
    }
    else {
        '(none)'
    }

    $healthBlock = ''
    if ($health) {
        $rows = ($health.Checks | ForEach-Object {
            $mark = if ($_.Ok) { 'OK' } else { 'FAIL' }
            "| $($_.Name) | $mark | $($_.Detail) |"
        }) -join "`n"
        $healthBlock = @"

## Health
**OverallOk**: $($health.OverallOk)

| Check | Result | Detail |
|-------|--------|--------|
$rows
"@
    }

    $content = @"
# FAFO Status Report
**Generated**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

| Field | Value |
|-------|-------|
| ToolboxRoot | $($status.ToolboxRoot) |
| Version | $($status.Version) |
| SecretsLoaded | $secretsText |
| GrokOnPath | $($status.GrokOnPath) |
| PythonOnPath | $($status.PythonOnPath) |
| ReportDirsExist | $($status.ReportDirsExist) |
| SecretsModulePresent | $($status.SecretsModulePresent) |
| ToolboxModulePresent | $($status.ToolboxModulePresent) |
$healthBlock
"@

    $raw = if ($health) {
        [PSCustomObject]@{ Status = $status; Health = $health }
    }
    else {
        $status
    }

    Write-FAFOReport -Name $Name -Content $content -RawObject $raw -ToolboxRoot $ToolboxRoot
}

function Invoke-FAFOGrokDiag {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $scriptPath = $paths.InspectScript

    if (-not (Test-Path $scriptPath)) {
        throw "Diagnostic script not found: $scriptPath"
    }

    Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot | Out-Null
    Write-FAFOLog -Level Info -Message "Running Grok diagnostic: $scriptPath" -ToolboxRoot $ToolboxRoot

    Write-Host "=== FAFO Grok Diagnostic ===" -ForegroundColor Cyan
    & $scriptPath -ToolboxRoot $ToolboxRoot

    $status = Get-FAFOStatus -ToolboxRoot $ToolboxRoot
    $summary = @"
# Grok Diagnostic Wrapper
**Generated**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
**Toolbox**: $ToolboxRoot
**Inspect script**: $scriptPath

## Status snapshot
- SecretsLoaded: $($status.SecretsLoaded -join ', ')
- GrokOnPath: $($status.GrokOnPath)
- ReportDirsExist: $($status.ReportDirsExist)

Full install report was written by Inspect-GrokInstall.ps1 under Reports\Markdown and Reports\Raw.
"@

    $wrapper = Write-FAFOReport -Name 'GrokDiag-Wrapper' -Content $summary -RawObject $status -ToolboxRoot $ToolboxRoot

    [PSCustomObject]@{
        ToolboxRoot   = $ToolboxRoot
        DeviceId      = $paths.DeviceId
        InspectScript = $scriptPath
        Status        = $status
        WrapperReport = $wrapper
    }
}

function Invoke-FAFOSystemDiagnostics {
    <#
    .SYNOPSIS
      One-shot PC health / diagnostics collection for THIS machine only.
    .DESCRIPTION
      Runs Scripts\Invoke-FAFOSystemDiagnostics.ps1 — collects system status,
      writes device-local reports, rebuilds the PC Report Library catalog for
      this host, and prints a plain-English status summary.
      Safe for Grok CLI: user does not need to name individual tests.
    #>
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot),
        [switch]$OpenViewer,
        [switch]$SkipEventLog
    )

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $scriptPath = $paths.DiagScript
    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "System diagnostics script not found: $scriptPath"
    }

    Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot | Out-Null
    Write-FAFOLog -Level Info -Message "Running system diagnostics for device $($paths.DeviceId)" -ToolboxRoot $ToolboxRoot

    $argList = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $scriptPath,
        '-ToolboxRoot', $ToolboxRoot
    )
    if ($OpenViewer) { $argList += '-OpenViewer' }
    if ($SkipEventLog) { $argList += '-SkipEventLog' }

    & powershell.exe @argList
}

#endregion

#region Reports

function New-FAFOReportName {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [ValidateSet('md', 'json', 'txt')]
        [string]$Extension = 'md',

        [datetime]$Timestamp = (Get-Date)
    )

    $safeName = ($Name -replace '[^\w\-]+', '-').Trim('-')
    if (-not $safeName) { $safeName = 'Report' }

    $stamp = $Timestamp.ToString('yyyyMMdd-HHmmss')
    $ext = $Extension.TrimStart('.')

    [PSCustomObject]@{
        BaseName  = $safeName
        Timestamp = $stamp
        FileName  = "$safeName-$stamp.$ext"
        Stem      = "$safeName-$stamp"
    }
}

function Write-FAFOReport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [Parameter(Mandatory)]
        [string]$Content,

        [object]$RawObject,

        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot
    $stamp = Get-Date
    $mdName = New-FAFOReportName -Name $Name -Extension md -Timestamp $stamp

    $mdPath = Join-Path $paths.MarkdownDir $mdName.FileName
    $Content | Out-File -FilePath $mdPath -Encoding utf8

    $rawPath = $null
    if ($PSBoundParameters.ContainsKey('RawObject') -and $null -ne $RawObject) {
        $rawName = New-FAFOReportName -Name $Name -Extension json -Timestamp $stamp
        $rawPath = Join-Path $paths.RawDir $rawName.FileName
        $RawObject | ConvertTo-Json -Depth 8 | Out-File -FilePath $rawPath -Encoding utf8
    }

    Write-FAFOLog -Level Info -Message "Report written: $mdPath" -ToolboxRoot $ToolboxRoot -NoFile:$false
    if ($rawPath) {
        Write-Host "Raw written:    $rawPath" -ForegroundColor Green
    }

    [PSCustomObject]@{
        Name         = $mdName.BaseName
        Timestamp    = $mdName.Timestamp
        MarkdownPath = $mdPath
        RawPath      = $rawPath
    }
}

function Get-FAFOReport {
    [CmdletBinding()]
    param(
        [string]$Name,
        [ValidateSet('Markdown', 'Raw', 'All')]
        [string]$Kind = 'All',
        [int]$Last = 0,
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot
    $dirs = switch ($Kind) {
        'Markdown' { @($paths.MarkdownDir) }
        'Raw'      { @($paths.RawDir) }
        default    { @($paths.MarkdownDir, $paths.RawDir) }
    }

    $items = foreach ($dir in $dirs) {
        if (-not (Test-Path -LiteralPath $dir)) { continue }
        Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue | ForEach-Object {
            [PSCustomObject]@{
                Name         = $_.Name
                FullName     = $_.FullName
                Kind         = if ($_.DirectoryName -like '*Markdown*') { 'Markdown' } else { 'Raw' }
                Length       = $_.Length
                LastWriteTime = $_.LastWriteTime
            }
        }
    }

    if ($Name) {
        $items = $items | Where-Object { $_.Name -like "*$Name*" }
    }

    $items = $items | Sort-Object LastWriteTime -Descending
    if ($Last -gt 0) {
        $items = $items | Select-Object -First $Last
    }

    $items
}

function Remove-FAFOReport {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
    param(
        [string]$Name,
        [int]$OlderThanDays = 0,
        [ValidateSet('Markdown', 'Raw', 'All')]
        [string]$Kind = 'All',
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    if (-not $Name -and $OlderThanDays -le 0) {
        throw 'Specify -Name and/or -OlderThanDays (greater than 0).'
    }

    $cutoff = if ($OlderThanDays -gt 0) { (Get-Date).AddDays(-$OlderThanDays) } else { $null }
    $candidates = Get-FAFOReport -Name $Name -Kind $Kind -ToolboxRoot $ToolboxRoot

    if ($cutoff) {
        $candidates = $candidates | Where-Object { $_.LastWriteTime -lt $cutoff }
    }

    $removed = [System.Collections.Generic.List[string]]::new()
    foreach ($item in $candidates) {
        if ($PSCmdlet.ShouldProcess($item.FullName, 'Remove FAFO report')) {
            Remove-Item -LiteralPath $item.FullName -Force
            $removed.Add($item.FullName) | Out-Null
            Write-FAFOLog -Level Warn -Message "Removed report: $($item.FullName)" -ToolboxRoot $ToolboxRoot
        }
    }

    [PSCustomObject]@{
        RemovedCount = $removed.Count
        Removed      = @($removed)
    }
}

function Compress-FAFOReport {
    [CmdletBinding()]
    param(
        [int]$OlderThanDays = 30,
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot
    $cutoff = (Get-Date).AddDays(-$OlderThanDays)
    $toArchive = @(Get-FAFOReport -Kind All -ToolboxRoot $ToolboxRoot | Where-Object { $_.LastWriteTime -lt $cutoff })

    if ($toArchive.Count -eq 0) {
        Write-FAFOLog -Level Info -Message "No reports older than $OlderThanDays days to archive." -ToolboxRoot $ToolboxRoot
        return [PSCustomObject]@{
            ZipPath      = $null
            FileCount    = 0
            OlderThanDays = $OlderThanDays
        }
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $zipPath = Join-Path $paths.ArchiveDir "FAFO-Reports-$stamp.zip"
    $stage = Join-Path $env:TEMP ("FAFO-Archive-Stage-$stamp")
    New-Item -Path $stage -ItemType Directory -Force | Out-Null

    try {
        foreach ($f in $toArchive) {
            $sub = Join-Path $stage $f.Kind
            if (-not (Test-Path $sub)) { New-Item -Path $sub -ItemType Directory -Force | Out-Null }
            Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $sub $f.Name) -Force
        }

        Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zipPath -Force

        foreach ($f in $toArchive) {
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue
        }

        Write-FAFOLog -Level Info -Message "Archived $($toArchive.Count) report(s) -> $zipPath" -ToolboxRoot $ToolboxRoot
    }
    finally {
        Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }

    [PSCustomObject]@{
        ZipPath       = $zipPath
        FileCount     = $toArchive.Count
        OlderThanDays = $OlderThanDays
    }
}

function Open-FAFOPath {
    [CmdletBinding()]
    param(
        [ValidateSet('Root', 'Device', 'Reports', 'Markdown', 'Raw', 'PcReports', 'Logs', 'Backups', 'Archive', 'Server', 'Scripts', 'SecretsStore', 'Viewer', 'VerifoneSites', 'VerifoneLibrary')]
        [string]$Which = 'Root',
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $local = Get-FAFOLocalPaths -ToolboxRoot $ToolboxRoot
    $map = @{
        Root            = $paths.ToolboxRoot
        Device          = $paths.DeviceRoot
        Reports         = $paths.Reports
        Markdown        = $paths.Markdown
        Raw             = $paths.Raw
        PcReports       = $paths.PcReports
        Logs            = $paths.Logs
        Backups         = $paths.Backups
        Archive         = $paths.Archive
        Server          = $paths.Server
        Scripts         = $paths.Scripts
        SecretsStore    = $paths.SecretsStore
        Viewer          = $paths.PcReportViewer
        VerifoneSites   = $local.VerifoneSitesRoot
        VerifoneLibrary = $paths.VerifoneLibraryShell
    }

    $target = $map[$Which]
    if (-not (Test-Path -LiteralPath $target)) {
        if ($Which -in @('Logs', 'Backups', 'Archive', 'Markdown', 'Raw', 'Reports', 'Device', 'PcReports', 'VerifoneSites')) {
            Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot | Out-Null
            if ($Which -eq 'VerifoneSites') {
                $target = (Get-FAFOLocalPaths -ToolboxRoot $ToolboxRoot).VerifoneSitesRoot
            }
        }
        else {
            throw "Path not found: $target"
        }
    }

    Start-Process explorer.exe -ArgumentList $target
    Write-FAFOLog -Level Info -Message "Opened Explorer: $target" -ToolboxRoot $ToolboxRoot
    return $target
}

#endregion

#region Device profiles & connection testing (field tech)

# Session-selected profile (set by Select-FAFODeviceProfile)
$script:FAFOSelectedDeviceProfile = $null

function Get-FAFODeviceProfileCatalog {
    <#
    .SYNOPSIS
      Built-in petro/POS device profiles with sensible field defaults.
    .NOTES
      IPs/ports are starting points — site networks vary. Always confirm on-site.
    #>
    @(
        [PSCustomObject]@{
            Id              = 'gilbarco-passport'
            Name            = 'Gilbarco Passport'
            Vendor          = 'Gilbarco'
            Category        = 'POS / Back Office'
            DefaultIP       = '192.168.1.50'
            SuggestedRange  = '192.168.1.0/24 (store LAN)'
            CommonPorts     = @(80, 443, 7001, 8080)
            PortNotes       = '80/443 web UI; 7001 common Passport service; 8080 alternate web'
            Notes           = 'Passport POS / Manager workstation. Confirm IP with site router or Passport network config.'
        }
        [PSCustomObject]@{
            Id              = 'gilbarco-flexpay4'
            Name            = 'Gilbarco FlexPay 4'
            Vendor          = 'Gilbarco'
            Category        = 'Outdoor Payment Terminal'
            DefaultIP       = '192.168.1.100'
            SuggestedRange  = '192.168.1.0/24 (forecourt / OPT VLAN if used)'
            CommonPorts     = @(80, 443, 22, 10001)
            PortNotes       = '80/443 device web; 22 SSH (if enabled); 10001 site/host style TCP'
            Notes           = 'FlexPay IV outdoor terminal. May sit on a separate forecourt switch/VLAN.'
        }
        [PSCustomObject]@{
            Id              = 'verifone-common'
            Name            = 'Verifone (common defaults)'
            Vendor          = 'Verifone'
            Category        = 'POS / Site Controller'
            DefaultIP       = '192.168.1.60'
            SuggestedRange  = '192.168.1.0/24 (store LAN)'
            CommonPorts     = @(80, 443, 5015, 9001)
            PortNotes       = '80/443 web/admin; 5015 common Verifone service; 9001 site-dependent'
            Notes           = 'Generic Verifone baseline (Commander/Ruby-class sites). Verify model-specific ports on site docs.'
        }
        [PSCustomObject]@{
            Id              = 'omnia-2000'
            Name            = 'OMNIA 2000'
            Vendor          = 'Gilbarco'
            Category        = 'ATG / Tank Gauge'
            DefaultIP       = '192.168.1.20'
            SuggestedRange  = '192.168.1.0/24 (back room / ATG)'
            CommonPorts     = @(10001, 80, 443)
            PortNotes       = '10001 TLS-style ATG TCP (common); 80/443 web if enabled'
            Notes           = 'OMNIA 2000 automatic tank gauge. Serial-to-IP converters may change the IP; port 10001 is the usual first check.'
        }
        [PSCustomObject]@{
            Id              = 'omnia-3000'
            Name            = 'OMNIA 3000'
            Vendor          = 'Gilbarco'
            Category        = 'ATG / Tank Gauge'
            DefaultIP       = '192.168.1.30'
            SuggestedRange  = '192.168.1.0/24 (back room / ATG)'
            CommonPorts     = @(10001, 80, 443)
            PortNotes       = '10001 TLS-style ATG TCP (common); 80/443 web if enabled'
            Notes           = 'OMNIA 3000 automatic tank gauge. Same network habits as 2000; confirm firmware/web features per site.'
        }
    )
}

function Get-FAFODeviceProfile {
    <#
    .SYNOPSIS
      List built-in device profiles, or return one by name/id.
    .EXAMPLE
      Get-FAFODeviceProfile
      Get-FAFODeviceProfile -Name 'OMNIA 3000'
      Get-FAFODeviceProfile -Name passport
    #>
    [CmdletBinding()]
    param(
        [string]$Name,
        [switch]$Selected
    )

    if ($Selected) {
        if ($script:FAFOSelectedDeviceProfile) {
            return $script:FAFOSelectedDeviceProfile
        }
        Write-Warning 'No device profile selected. Use Select-FAFODeviceProfile first.'
        return $null
    }

    $all = Get-FAFODeviceProfileCatalog

    if (-not $Name) {
        return $all
    }

    $q = $Name.Trim()
    $match = $all | Where-Object {
        $_.Name -eq $q -or
        $_.Id -eq $q -or
        $_.Name -like "*$q*" -or
        $_.Id -like "*$q*"
    }

    if (-not $match) {
        Write-Warning "No device profile matched '$Name'. Use Get-FAFODeviceProfile to list names."
        return @()
    }

    # Prefer exact name/id, then first partial
    $exact = @($match | Where-Object { $_.Name -eq $q -or $_.Id -eq $q })
    if ($exact.Count -eq 1) { return $exact[0] }
    if ($match.Count -eq 1) { return $match[0] }
    return $match
}

function Select-FAFODeviceProfile {
    <#
    .SYNOPSIS
      Select a device profile by name, or interactively from a menu.
    .EXAMPLE
      Select-FAFODeviceProfile -Name 'Gilbarco Passport'
      Select-FAFODeviceProfile   # interactive menu
    #>
    [CmdletBinding()]
    param(
        [string]$Name
    )

    $all = @(Get-FAFODeviceProfileCatalog)
    $chosen = $null

    if ($Name) {
        $result = Get-FAFODeviceProfile -Name $Name
        if ($result -is [System.Array] -and $result.Count -gt 1) {
            Write-Host "Multiple matches for '$Name':" -ForegroundColor Yellow
            $result | ForEach-Object { Write-Host "  - $($_.Name) [$($_.Id)]" }
            throw "Ambiguous profile name '$Name'. Be more specific."
        }
        if (-not $result -or ($result -is [System.Array] -and $result.Count -eq 0)) {
            throw "Profile not found: $Name"
        }
        $chosen = if ($result -is [System.Array]) { $result[0] } else { $result }
    }
    else {
        Write-Host ''
        Write-Host 'FAFO Device Profiles' -ForegroundColor Cyan
        Write-Host '-------------------'
        for ($i = 0; $i -lt $all.Count; $i++) {
            $p = $all[$i]
            Write-Host ("[{0}] {1,-28}  default {2,-15}  ports {3}" -f ($i + 1), $p.Name, $p.DefaultIP, ($p.CommonPorts -join ','))
        }
        Write-Host ''
        $raw = Read-Host 'Select profile number (or blank to cancel)'
        if ([string]::IsNullOrWhiteSpace($raw)) {
            Write-Host 'Selection cancelled.' -ForegroundColor Yellow
            return $null
        }
        $num = 0
        if (-not [int]::TryParse($raw, [ref]$num) -or $num -lt 1 -or $num -gt $all.Count) {
            throw "Invalid selection: $raw"
        }
        $chosen = $all[$num - 1]
    }

    $script:FAFOSelectedDeviceProfile = $chosen
    $env:FAFO_DEVICE_PROFILE = $chosen.Id
    $env:FAFO_DEVICE_IP = $chosen.DefaultIP

    Write-Host ("Selected: {0}  |  Default IP: {1}  |  Ports: {2}" -f `
            $chosen.Name, $chosen.DefaultIP, ($chosen.CommonPorts -join ', ')) -ForegroundColor Green
    Write-FAFOLog -Level Info -Message "Device profile selected: $($chosen.Name) ($($chosen.Id))" -NoFile:$false

    return $chosen
}

function Get-FAFOConnectionTest {
    <#
    .SYNOPSIS
      Test reachability of any host: ICMP ping + TCP port check(s).
    .DESCRIPTION
      Independent of device profiles — pass any IP and port(s).
      Optionally use -ProfileName / -UseSelectedProfile for default IP/ports.
    .EXAMPLE
      Get-FAFOConnectionTest -IPAddress 192.168.1.20 -Port 10001
      Get-FAFOConnectionTest -IPAddress 10.0.0.5 -Port 80,443
      Get-FAFOConnectionTest -ProfileName 'OMNIA 2000'
      Get-FAFOConnectionTest -UseSelectedProfile
    #>
    [CmdletBinding(DefaultParameterSetName = 'Manual')]
    param(
        [Parameter(ParameterSetName = 'Manual', Mandatory)]
        [Alias('ComputerName', 'Host', 'IP')]
        [string]$IPAddress,

        [Parameter(ParameterSetName = 'Manual')]
        [int[]]$Port = @(80),

        [Parameter(ParameterSetName = 'Profile')]
        [string]$ProfileName,

        [Parameter(ParameterSetName = 'Selected')]
        [switch]$UseSelectedProfile,

        [Parameter(ParameterSetName = 'Profile')]
        [Parameter(ParameterSetName = 'Selected')]
        [string]$OverrideIP,

        [int]$TimeoutMs = 3000,

        [switch]$SkipPing
    )

    $profileUsed = $null
    $targetIp = $IPAddress
    $ports = @($Port)

    if ($PSCmdlet.ParameterSetName -eq 'Profile') {
        $profileUsed = Get-FAFODeviceProfile -Name $ProfileName
        if (-not $profileUsed -or ($profileUsed -is [System.Array] -and $profileUsed.Count -ne 1)) {
            if ($profileUsed -is [System.Array] -and $profileUsed.Count -gt 1) {
                throw "Ambiguous profile '$ProfileName'. Pick an exact name."
            }
            throw "Profile not found: $ProfileName"
        }
        if ($profileUsed -is [System.Array]) { $profileUsed = $profileUsed[0] }
        $targetIp = if ($OverrideIP) { $OverrideIP } else { $profileUsed.DefaultIP }
        $ports = @($profileUsed.CommonPorts)
    }
    elseif ($PSCmdlet.ParameterSetName -eq 'Selected') {
        $profileUsed = Get-FAFODeviceProfile -Selected
        if (-not $profileUsed) {
            throw 'No profile selected. Run Select-FAFODeviceProfile first, or pass -IPAddress/-Port.'
        }
        $targetIp = if ($OverrideIP) { $OverrideIP } else { $profileUsed.DefaultIP }
        $ports = @($profileUsed.CommonPorts)
    }

    if ([string]::IsNullOrWhiteSpace($targetIp)) {
        throw 'IPAddress is required.'
    }
    if (-not $ports -or $ports.Count -eq 0) {
        $ports = @(80)
    }

    $pingOk = $null
    $pingMs = $null
    $pingError = $null

    if (-not $SkipPing) {
        try {
            # -Count 1, quiet; TimeoutSeconds best-effort (PS7+)
            $pingParams = @{
                ComputerName = $targetIp
                Count        = 1
                Quiet        = $true
                ErrorAction  = 'Stop'
            }
            if ((Get-Command Test-Connection).Parameters.ContainsKey('TimeoutSeconds')) {
                $pingParams['TimeoutSeconds'] = [Math]::Max(1, [int][Math]::Ceiling($TimeoutMs / 1000.0))
            }
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            $pingOk = Test-Connection @pingParams
            $sw.Stop()
            $pingMs = [int]$sw.ElapsedMilliseconds
        }
        catch {
            $pingOk = $false
            $pingError = $_.Exception.Message
        }
    }

    $results = foreach ($p in $ports) {
        $tcpOk = $false
        $tcpMs = $null
        $tcpError = $null
        $swTcp = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $client = [System.Net.Sockets.TcpClient]::new()
            $async = $client.BeginConnect($targetIp, [int]$p, $null, $null)
            $waited = $async.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
            if (-not $waited) {
                $tcpOk = $false
                $tcpError = "TCP timeout after ${TimeoutMs}ms"
                try { $client.Close() } catch { }
            }
            else {
                try {
                    $client.EndConnect($async)
                    $tcpOk = $client.Connected
                }
                catch {
                    $tcpOk = $false
                    $tcpError = $_.Exception.Message
                }
                finally {
                    try { $client.Close() } catch { }
                    try { $client.Dispose() } catch { }
                }
            }
        }
        catch {
            $tcpOk = $false
            $tcpError = $_.Exception.Message
        }
        finally {
            $swTcp.Stop()
            $tcpMs = [int]$swTcp.ElapsedMilliseconds
        }

        [PSCustomObject]@{
            IPAddress     = $targetIp
            Port          = [int]$p
            PingOk        = $pingOk
            PingMs        = $pingMs
            PingError     = $pingError
            TcpOk         = $tcpOk
            TcpMs         = $tcpMs
            TcpError      = $tcpError
            OverallOk     = ($(if ($SkipPing) { $tcpOk } else { $pingOk -and $tcpOk }))
            ProfileName   = if ($profileUsed) { $profileUsed.Name } else { $null }
            TestedAt      = Get-Date
            TimeoutMs     = $TimeoutMs
        }
    }

    $list = @($results)
    $open = @($list | Where-Object TcpOk | ForEach-Object { $_.Port })
    $summary = 'FAIL'
    if ($list.Count -gt 0 -and ($list | Where-Object TcpOk).Count -eq $list.Count) {
        $summary = 'ALL_TCP_OK'
    }
    elseif ($open.Count -gt 0) {
        $summary = 'PARTIAL'
    }

    Write-Host ("Connection test {0}:{1}  ping={2}  tcp_open=[{3}]  ({4})" -f `
            $targetIp,
        ($ports -join ','),
        $(if ($SkipPing) { 'skipped' } elseif ($pingOk) { 'ok' } else { 'fail' }),
        ($open -join ','),
        $summary
    ) -ForegroundColor $(if ($summary -eq 'ALL_TCP_OK') { 'Green' } elseif ($summary -eq 'PARTIAL') { 'Yellow' } else { 'Red' })

    Write-FAFOLog -Level Info -Message ("ConnectionTest {0} ports={1} result={2}" -f $targetIp, ($ports -join ','), $summary)

    # Single port → single object; multi → array (caller friendly)
    if ($list.Count -eq 1) { return $list[0] }
    return $list
}

#endregion

Export-ModuleMember -Function @(
    # Paths & config
    'Get-FAFOToolboxRoot',
    'Set-FAFOToolboxRoot',
    'Get-FAFODeviceId',
    'Get-FAFOCommonPaths',
    'Get-FAFOLocalPathsConfigPath',
    'Get-FAFOLocalPaths',
    'Save-FAFOLocalPaths',
    'Select-FAFOFolder',
    'Initialize-FAFODirectoryJunction',
    'Initialize-FAFOPaths',
    'Get-FAFOEnvironment',
    # Logging
    'Write-FAFOLog',
    # Safe file ops
    'Backup-FAFOItem',
    'Move-FAFOItem',
    'Copy-FAFOItem',
    # Diagnostics
    'Get-FAFOStatus',
    'Test-FAFOHealth',
    'Write-FAFOStatusReport',
    'Invoke-FAFOGrokDiag',
    'Invoke-FAFOSystemDiagnostics',
    # Reports
    'New-FAFOReportName',
    'Write-FAFOReport',
    'Get-FAFOReport',
    'Remove-FAFOReport',
    'Compress-FAFOReport',
    'Open-FAFOPath',
    # Device profiles & connectivity
    'Get-FAFODeviceProfile',
    'Select-FAFODeviceProfile',
    'Get-FAFOConnectionTest'
)

