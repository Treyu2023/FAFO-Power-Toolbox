#Requires -RunAsAdministrator
param(
    [switch]$IncludeUsb,
    [switch]$RemoveDrivers
)

<#
.SYNOPSIS
    Safely removes phantom (ghost) Plug and Play devices from Windows.
#>

$ErrorActionPreference = 'Continue'

$LogDir  = Join-Path $PSScriptRoot 'logs'
$LogFile = Join-Path $LogDir ("ghost-clean-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Log {
    param([string]$Message, [string]$Color = 'White')
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message
    Add-Content -Path $LogFile -Value $line
    Write-Host $line -ForegroundColor $Color
}

# Default: monitor/display ghosts + stacked PlayStation VR2 entries (USBDevice class).
# Pass -IncludeUsb to also list other USB/virtual ghosts.
$IncludeUsbGhosts = $IncludeUsb.IsPresent -or ($env:GHOST_CLEANER_INCLUDE_USB -eq '1')
$SafeClasses = if ($IncludeUsbGhosts) {
    @('Monitor', 'Display', 'USB', 'USBDevice', 'HIDClass', 'Bluetooth', 'SoftwareDevice', 'AudioEndpoint', 'Media', 'Sensor', 'Camera')
} else {
    @('Monitor', 'Display', 'USBDevice')
}

$PlayStationNamePattern = '(?i)(playstation|ps\s*vr2?|psvr2?|sense\s*controller|\bps\s*vr\b)'
$PlayStationInstancePattern = 'VID_054C'

$SafeClassSet = [System.Collections.Generic.HashSet[string]]::new(
    [string[]]$SafeClasses,
    [StringComparer]::OrdinalIgnoreCase
)

function Test-IsPlayStationDevice {
    param($Device)

    $name = [string]$Device.FriendlyName
    $id = [string]$Device.InstanceId
    if ($id -match $PlayStationInstancePattern) { return $true }
    if ($name -match $PlayStationNamePattern) { return $true }
    return $false
}

function Test-IsActivePlayStationDevice {
    param($Device)

    if (-not (Test-IsPlayStationDevice $Device)) { return $false }
    $problem = [string]$Device.Problem
    return (
        $Device.Status -eq 'OK' -and
        ($problem -eq 'CM_PROB_NONE' -or [string]::IsNullOrWhiteSpace($problem))
    )
}

function Get-DeviceRisk {
    param($Device)
    if (Test-IsPlayStationDevice $Device) {
        if ($Device.Class -eq 'Bluetooth') { return 'Low (PS controller — skip if connected)' }
        return 'Low (stacked PS VR2 ghost)'
    }
    switch ($Device.Class) {
        'Monitor' { return 'Low (display ghost)' }
        'Display' { return 'Low (GPU ghost)' }
        'USB' { return 'Medium (old USB ghost)' }
        'USBDevice' { return 'Medium (USB interface ghost)' }
        'SoftwareDevice' { return 'Medium (virtual device)' }
        default { return 'Review carefully' }
    }
}

function Test-SafeGhostRemoval {
    param($Device)

    if ($Device.InstanceId -match '^(ROOT|ACPI|HTREE)\\') { return $false }

    $isPhantom = ($Device.Problem -eq 'CM_PROB_PHANTOM') -or ($Device.Status -eq 'Unknown')
    $isPlayStation = Test-IsPlayStationDevice $Device

    if ($isPlayStation) {
        if (Test-IsActivePlayStationDevice $Device) { return $false }
        if ($isPhantom -or $Device.Status -in @('Error', 'Degraded')) { return $true }
        return $false
    }

    if ($Device.Status -eq 'OK') { return $false }
    if (-not $isPhantom) { return $false }
    if (-not $SafeClassSet.Contains($Device.Class)) { return $false }
    if ($Device.Class -eq 'Display' -and $Device.FriendlyName -match 'NVIDIA') { return $false }

    return $true
}

function Get-DeviceDriverInf {
    param([string]$InstanceId)

    $prop = Get-PnpDeviceProperty -InstanceId $InstanceId -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction SilentlyContinue
    if ($prop -and $prop.Data) {
        $leaf = Split-Path -Leaf ([string]$prop.Data)
        if ($leaf -match '\.inf$') { return $leaf }
    }

    $enumPath = Join-Path 'HKLM:\SYSTEM\CurrentControlSet\Enum' $InstanceId
    $driverKey = Get-ItemProperty -Path $enumPath -Name 'Driver' -ErrorAction SilentlyContinue
    if ($driverKey -and $driverKey.Driver) {
        $driverRegPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\$($driverKey.Driver)"
        $infKey = Get-ItemProperty -Path $driverRegPath -Name 'InfPath' -ErrorAction SilentlyContinue
        if ($infKey -and $infKey.InfPath) {
            $leaf = Split-Path -Leaf ([string]$infKey.InfPath)
            if ($leaf -match '\.inf$') { return $leaf }
        }
    }

    $signed = Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue |
        Where-Object { $_.DeviceID -eq $InstanceId } |
        Select-Object -First 1
    if ($signed -and $signed.InfName) {
        return [string]$signed.InfName
    }

    return $null
}

function Add-DeviceDriverInfo {
    param($Device)

    $driverInf = Get-DeviceDriverInf -InstanceId $Device.InstanceId
    $Device | Add-Member -NotePropertyName DriverInf -NotePropertyValue $driverInf -Force
    $Device | Add-Member -NotePropertyName DriverAvailable -NotePropertyValue ([bool]$driverInf) -Force
    return $Device
}

function Remove-GhostDevice {
    param(
        [string]$InstanceId,
        [string]$FriendlyName,
        [switch]$AlsoRemoveDriver,
        [string]$DriverInf
    )

    $pnputil = Join-Path $env:Windir 'System32\pnputil.exe'
    if (-not (Test-Path $pnputil)) {
        throw 'pnputil.exe is not available on this system.'
    }

    $output = & $pnputil /remove-device $InstanceId 2>&1
    if ($LASTEXITCODE -ne 0) {
        $text = ($output | Out-String).Trim()
        if ($text) { throw $text }
        throw "pnputil failed with exit code $LASTEXITCODE for $FriendlyName"
    }

    if ($AlsoRemoveDriver -and $DriverInf) {
        $driverOutput = & $pnputil /delete-driver $DriverInf /uninstall /force 2>&1
        if ($LASTEXITCODE -ne 0) {
            $text = ($driverOutput | Out-String).Trim()
            if ($text) { throw "Device removed but driver delete failed: $text" }
            throw "Device removed but driver delete failed with exit code $LASTEXITCODE for $DriverInf"
        }
    }
}

function ConvertTo-RemovalPlan {
    param(
        [array]$Devices,
        [array]$DriverDeviceIndices = @()
    )

    $driverSet = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($idx in $DriverDeviceIndices) { [void]$driverSet.Add($idx) }

    return @(
        for ($i = 0; $i -lt $Devices.Count; $i++) {
            $dev = $Devices[$i]
            [PSCustomObject]@{
                Device       = $dev
                RemoveDriver = $driverSet.Contains($i) -and $dev.DriverAvailable
                DriverInf    = $dev.DriverInf
            }
        }
    )
}

function Parse-SelectionIndices {
    param(
        [string]$InputText,
        [int]$MaxCount
    )

    if ([string]::IsNullOrWhiteSpace($InputText)) { return @() }
    if ($InputText.Trim().Equals('ALL', [System.StringComparison]::OrdinalIgnoreCase)) {
        return @(0..($MaxCount - 1))
    }

    $indices = @()
    foreach ($part in ($InputText -split ',')) {
        $n = 0
        if ([int]::TryParse($part.Trim(), [ref]$n) -and $n -ge 1 -and $n -le $MaxCount) {
            $indices += ($n - 1)
        }
    }

    return @($indices | Sort-Object -Unique)
}

function Select-DevicesConsole {
    param(
        [array]$Candidates,
        [switch]$RemoveDriversForAll
    )

    Write-Log 'Console selection mode' 'Yellow'
    Write-Log 'Enter device numbers to remove (e.g. 1,3,5), ALL, or press Enter to cancel.' 'DarkGray'
    Write-Host ''

    for ($i = 0; $i -lt $Candidates.Count; $i++) {
        $dev = $Candidates[$i]
        Write-Host ("  [{0,2}] [{1}] {2}" -f ($i + 1), $dev.Class, $dev.FriendlyName) -ForegroundColor White
        Write-Host ("       Risk: {0}" -f (Get-DeviceRisk $dev)) -ForegroundColor DarkYellow
        if ($dev.DriverAvailable) {
            Write-Host ("       Driver: {0}" -f $dev.DriverInf) -ForegroundColor DarkCyan
        } else {
            Write-Host '       Driver: (none detected)' -ForegroundColor DarkGray
        }
        Write-Host ("       {0}" -f $dev.InstanceId) -ForegroundColor DarkGray
    }

    Write-Host ''
    $deviceInput = Read-Host 'Devices to remove'
    $deviceIndices = Parse-SelectionIndices -InputText $deviceInput -MaxCount $Candidates.Count
    if ($deviceIndices.Count -eq 0) { return @() }

    $selected = @($deviceIndices | ForEach-Object { $Candidates[$_] })
    $withDrivers = @(
        for ($i = 0; $i -lt $selected.Count; $i++) {
            if ($selected[$i].DriverAvailable) { $i }
        }
    )

    if ($withDrivers.Count -eq 0 -or $RemoveDriversForAll) {
        $driverIndices = if ($RemoveDriversForAll) {
            @(0..($selected.Count - 1))
        } else {
            @()
        }
        return ConvertTo-RemovalPlan -Devices $selected -DriverDeviceIndices $driverIndices
    }

    Write-Host ''
    Write-Log 'Optional driver purge — enter numbers from your selection to also remove driver packages.' 'Yellow'
    Write-Log 'Use ALL for every selected device with a driver, or press Enter to skip driver removal.' 'DarkGray'
    for ($i = 0; $i -lt $selected.Count; $i++) {
        $dev = $selected[$i]
        if (-not $dev.DriverAvailable) { continue }
        Write-Host ("  [{0,2}] {1} -> {2}" -f ($i + 1), $dev.FriendlyName, $dev.DriverInf) -ForegroundColor DarkCyan
    }

    Write-Host ''
    $driverInput = Read-Host 'Also remove drivers for'
    $driverIndices = Parse-SelectionIndices -InputText $driverInput -MaxCount $selected.Count

    return ConvertTo-RemovalPlan -Devices $selected -DriverDeviceIndices $driverIndices
}

function Select-DevicesGrid {
    param(
        [array]$Candidates,
        [switch]$RemoveDriversForAll
    )

    $rows = $Candidates | ForEach-Object {
        [PSCustomObject]@{
            Risk        = Get-DeviceRisk $_
            Class       = $_.Class
            Name        = $_.FriendlyName
            Driver      = if ($_.DriverAvailable) { $_.DriverInf } else { '(none)' }
            Status      = $_.Status
            Problem     = $_.Problem
            InstanceId  = $_.InstanceId
            _Device     = $_
        }
    }

    Write-Log 'Opening device picker...' 'Yellow'
    Write-Log 'Select only the rows you want removed, then click OK.' 'DarkGray'
    Write-Log 'Driver column shows packages available for optional purge in the next step.' 'DarkGray'

    $picked = $rows | Out-GridView -Title 'Ghost Device Cleaner - Select devices to remove' -PassThru
    if (-not $picked) { return @() }

    $selected = @($picked | ForEach-Object { $_._Device })
    $withDrivers = @($selected | Where-Object { $_.DriverAvailable })

    if ($withDrivers.Count -eq 0 -or $RemoveDriversForAll) {
        $driverIndices = if ($RemoveDriversForAll) {
            @(0..($selected.Count - 1))
        } else {
            @()
        }
        return ConvertTo-RemovalPlan -Devices $selected -DriverDeviceIndices $driverIndices
    }

    $driverRows = $withDrivers | ForEach-Object {
        [PSCustomObject]@{
            Name       = $_.FriendlyName
            Class      = $_.Class
            Driver     = $_.DriverInf
            InstanceId = $_.InstanceId
            _Device    = $_
        }
    }

    Write-Log 'Opening driver purge picker...' 'Yellow'
    Write-Log 'Select which of your chosen devices should also have their driver package removed.' 'DarkGray'

    $driverPicked = $driverRows | Out-GridView -Title 'Ghost Device Cleaner - Also remove driver packages?' -PassThru
    $driverInstanceIds = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    if ($driverPicked) {
        foreach ($row in $driverPicked) {
            [void]$driverInstanceIds.Add([string]$row._Device.InstanceId)
        }
    }

    $driverIndices = @(
        for ($i = 0; $i -lt $selected.Count; $i++) {
            if ($driverInstanceIds.Contains([string]$selected[$i].InstanceId)) { $i }
        }
    )

    return ConvertTo-RemovalPlan -Devices $selected -DriverDeviceIndices $driverIndices
}

Clear-Host
Write-Log 'Ghost Device Cleaner' 'Cyan'
Write-Log "Log file: $LogFile" 'DarkGray'
if ($IncludeUsbGhosts) {
    Write-Log 'Mode: monitors + PlayStation VR2 + USB/virtual ghosts' 'Yellow'
} else {
    Write-Log 'Mode: monitor/display + PlayStation VR2 stacked ghosts (set GHOST_CLEANER_INCLUDE_USB=1 for all USB)' 'DarkGray'
}
Write-Log 'Scanning for phantom devices...' 'Yellow'

$allCandidates = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object {
    ($_.Problem -eq 'CM_PROB_PHANTOM') -or ($_.Status -eq 'Unknown')
}

$candidates = @(
    $allCandidates |
        Where-Object { Test-SafeGhostRemoval $_ } |
        Sort-Object @{
            Expression = {
                if (Test-IsPlayStationDevice $_) { 0 }
                elseif ($_.Class -eq 'Monitor') { 1 }
                elseif ($_.Class -eq 'Display') { 2 }
                else { 3 }
            }
        }, FriendlyName |
        ForEach-Object { Add-DeviceDriverInfo $_ }
)

if ($candidates.Count -eq 0) {
    Write-Log 'No safe ghost devices found in this mode. Display and PS VR2 ghosts may already be clean.' 'Green'
    if (-not $IncludeUsbGhosts) {
        Write-Log 'To scan other USB/virtual ghosts too, run Run-Cleaner-Include-USB.bat' 'DarkGray'
    }
    Read-Host 'Press Enter to close'
    exit 0
}

Write-Log ("Found {0} ghost device(s) eligible for removal." -f $candidates.Count) 'Yellow'
Write-Host ''

$useGrid = -not $env:GHOST_CLEANER_CONSOLE -and [Environment]::UserInteractive

try {
    $removalPlan = if ($useGrid) {
        Select-DevicesGrid -Candidates $candidates -RemoveDrivers:$RemoveDrivers.IsPresent
    } else {
        Select-DevicesConsole -Candidates $candidates -RemoveDriversForAll:$RemoveDrivers.IsPresent
    }
}
catch {
    Write-Log ("Grid picker unavailable ({0}). Falling back to console selection." -f $_.Exception.Message) 'Yellow'
    $removalPlan = Select-DevicesConsole -Candidates $candidates -RemoveDriversForAll:$RemoveDrivers.IsPresent
}

if ($removalPlan.Count -eq 0) {
    Write-Log 'No devices selected. No changes made.' 'Yellow'
    Read-Host 'Press Enter to close'
    exit 0
}

Write-Host ''
Write-Log ("You selected {0} device(s) for removal:" -f $removalPlan.Count) 'Cyan'
Write-Log ('-' * 72) 'DarkGray'

foreach ($item in $removalPlan) {
    $dev = $item.Device
    Write-Log ("  [{0}] {1}" -f $dev.Class, $dev.FriendlyName) 'White'
    Write-Log ("           Risk: {0}" -f (Get-DeviceRisk $dev)) 'DarkYellow'
    if ($item.RemoveDriver -and $item.DriverInf) {
        Write-Log ("           Driver purge: {0}" -f $item.DriverInf) 'DarkCyan'
    } else {
        Write-Log '           Driver purge: skipped' 'DarkGray'
    }
    Write-Log ("           {0}" -f $dev.InstanceId) 'DarkGray'
}

Write-Log ('-' * 72) 'DarkGray'
Write-Host ''
$driverCount = @($removalPlan | Where-Object { $_.RemoveDriver }).Count
$confirmPrompt = if ($driverCount -gt 0) {
    'Type YES to permanently remove the selected devices and purge their driver packages'
} else {
    'Type YES to permanently remove the selected devices'
}
$confirm = Read-Host $confirmPrompt

if ($confirm.Trim().ToUpperInvariant() -ne 'YES') {
    Write-Log 'Cancelled by user. No changes made.' 'Yellow'
    Read-Host 'Press Enter to close'
    exit 0
}

$removed = 0
$failed  = 0
$driversRemoved = 0
$driversFailed  = 0

foreach ($item in $removalPlan) {
    $dev = $item.Device
    try {
        $action = if ($item.RemoveDriver -and $item.DriverInf) {
            "Removing device + driver: {0}" -f $dev.FriendlyName
        } else {
            "Removing device: {0}" -f $dev.FriendlyName
        }
        Write-Log $action 'Cyan'
        Remove-GhostDevice -InstanceId $dev.InstanceId -FriendlyName $dev.FriendlyName `
            -AlsoRemoveDriver:($item.RemoveDriver -and $item.DriverInf) -DriverInf $item.DriverInf
        Write-Log '  -> Removed successfully' 'Green'
        $removed++
        if ($item.RemoveDriver -and $item.DriverInf) { $driversRemoved++ }
    }
    catch {
        Write-Log ("  -> Failed: {0}" -f $_.Exception.Message) 'Red'
        $failed++
        if ($item.RemoveDriver -and $item.DriverInf) { $driversFailed++ }
    }
}

Write-Log ('-' * 72) 'DarkGray'
$summary = "Done. Devices removed: $removed | Failed: $failed | Skipped: $($candidates.Count - $removalPlan.Count)"
if ($driverCount -gt 0) {
    $summary += " | Driver packages purged: $driversRemoved | Driver failures: $driversFailed"
}
Write-Log $summary $(if ($failed -eq 0) { 'Green' } else { 'Yellow' })

if ($removed -gt 0) {
    Write-Log 'A restart is recommended so Windows fully refreshes the display stack.' 'Yellow'
}

Read-Host 'Press Enter to close'