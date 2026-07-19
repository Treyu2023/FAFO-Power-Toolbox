# FAFO.Toolbox.psm1
# Paths, logging, safe file ops, health, and report helpers for FAFO Power Toolbox
# Version: 1.2.0

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

function Get-FAFOCommonPaths {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    [ordered]@{
        ToolboxRoot   = $ToolboxRoot
        Scripts       = Join-Path $ToolboxRoot 'Scripts'
        Modules       = Join-Path $ToolboxRoot 'Scripts\Modules'
        SecretsModule = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Secrets'
        ToolboxModule = Join-Path $ToolboxRoot 'Scripts\Modules\FAFO.Toolbox'
        Reports       = Join-Path $ToolboxRoot 'Reports'
        Markdown      = Join-Path $ToolboxRoot 'Reports\Markdown'
        Raw           = Join-Path $ToolboxRoot 'Reports\Raw'
        Archive       = Join-Path $ToolboxRoot 'Reports\Archive'
        Logs          = Join-Path $ToolboxRoot 'Logs'
        Backups       = Join-Path $ToolboxRoot 'Backups'
        Server        = Join-Path $ToolboxRoot 'server'
        Shared        = Join-Path $ToolboxRoot 'shared'
        SecretsStore  = Join-Path $env:LOCALAPPDATA 'FAFO\Secrets'
        GrokHome      = Join-Path $env:USERPROFILE '.grok'
        InspectScript = Join-Path $ToolboxRoot 'Scripts\Inspect-GrokInstall.ps1'
        SessionScript = Join-Path $ToolboxRoot 'Scripts\Initialize-FAFOSession.ps1'
        BindConfig    = Join-Path $ToolboxRoot 'shared\aitoolbox-bind.json'
        VersionFile   = Join-Path $ToolboxRoot 'VERSION'
    }
}

function Initialize-FAFOPaths {
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    foreach ($dir in @($paths.Markdown, $paths.Raw, $paths.Archive, $paths.Logs, $paths.Backups)) {
        if (-not (Test-Path -LiteralPath $dir)) {
            New-Item -Path $dir -ItemType Directory -Force | Out-Null
        }
    }

    [PSCustomObject]@{
        ToolboxRoot = $paths.ToolboxRoot
        MarkdownDir = $paths.Markdown
        RawDir      = $paths.Raw
        ArchiveDir  = $paths.Archive
        LogsDir     = $paths.Logs
        BackupsDir  = $paths.Backups
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
        InspectScript = $scriptPath
        Status        = $status
        WrapperReport = $wrapper
    }
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
        [ValidateSet('Root', 'Reports', 'Markdown', 'Raw', 'Logs', 'Backups', 'Archive', 'Server', 'Scripts', 'SecretsStore')]
        [string]$Which = 'Root',
        [string]$ToolboxRoot = (Get-FAFOToolboxRoot)
    )

    $paths = Get-FAFOCommonPaths -ToolboxRoot $ToolboxRoot
    $map = @{
        Root         = $paths.ToolboxRoot
        Reports      = $paths.Reports
        Markdown     = $paths.Markdown
        Raw          = $paths.Raw
        Logs         = $paths.Logs
        Backups      = $paths.Backups
        Archive      = $paths.Archive
        Server       = $paths.Server
        Scripts      = $paths.Scripts
        SecretsStore = $paths.SecretsStore
    }

    $target = $map[$Which]
    if (-not (Test-Path -LiteralPath $target)) {
        if ($Which -in @('Logs', 'Backups', 'Archive', 'Markdown', 'Raw', 'Reports')) {
            Initialize-FAFOPaths -ToolboxRoot $ToolboxRoot | Out-Null
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

Export-ModuleMember -Function @(
    # Paths & config
    'Get-FAFOToolboxRoot',
    'Set-FAFOToolboxRoot',
    'Get-FAFOCommonPaths',
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
    # Reports
    'New-FAFOReportName',
    'Write-FAFOReport',
    'Get-FAFOReport',
    'Remove-FAFOReport',
    'Compress-FAFOReport',
    'Open-FAFOPath'
)
