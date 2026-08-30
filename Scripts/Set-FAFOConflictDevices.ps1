#Requires -RunAsAdministrator
# Set-FAFOConflictDevices.ps1
# Keep Lian Li (L-Connect) + NZXT CAM as the only lighting stacks.
# Remove/disable Bluetooth PAN, ASUS AURA LED, and Sonic Studio leftovers
# that fight USB HID / audio / Bluetooth comms. Re-run at startup.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT,
    [switch]$InstallGuard,
    [switch]$UninstallGuard
)

$ErrorActionPreference = 'Continue'
$TaskName = 'FAFO-ConflictDeviceGuard'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}

$deviceId = ($env:COMPUTERNAME -replace '[^\w.\-]+', '-').Trim('-').ToUpperInvariant()
$logDir = Join-Path $env:LOCALAPPDATA "FAFO\Devices\$deviceId\Logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("conflict-devices-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))

function Write-Log {
    param([string]$Message, [string]$Color = 'White')
    $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $Message
    Add-Content -LiteralPath $logFile -Value $line
    Write-Host $line -ForegroundColor $Color
}

if ($UninstallGuard) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Log "Removed scheduled task $TaskName" 'Yellow'
    return
}

Write-Log '=== FAFO conflict-device pass ===' 'Cyan'
Write-Log "Log: $logFile"

# Do not touch working comms: ASUS USB-BT500, phone pairing, PS VR2, L-Connect, NZXT Kraken.
$keepName = '(?i)USB-BT500|RWK_S25|PlayStation|LianLi|L-Connect|NZXT|Kraken'
$targets = @(
    @{ Match = '(?i)Bluetooth Device \(Personal Area Network\)'; Also = 'BTH\\MS_BTHPAN\\'; Action = 'remove' },
    @{ Match = '(?i)^AURA LED Controller$'; Also = 'VID_0B05&PID_18F3&MI_00'; Action = 'disable' },
    @{ Match = '(?i)Sonic Studio Virtual Mixer'; Also = 'AVOLUTESS3VAD'; Action = 'remove' }
)

function Test-KeepDevice([string]$Name, [string]$Id) {
    return ($Name -match $keepName) -or ($Id -match $keepName)
}

function Invoke-DeviceOp {
    param(
        [ValidateSet('disable', 'remove')][string]$Op,
        [string]$InstanceId
    )
    try {
        if ($Op -eq 'disable') {
            Disable-PnpDevice -InstanceId $InstanceId -Confirm:$false -ErrorAction Stop
            return @{ Ok = $true; Text = 'Disable-PnpDevice' }
        }
        Remove-PnpDevice -InstanceId $InstanceId -Confirm:$false -ErrorAction Stop
        return @{ Ok = $true; Text = 'Remove-PnpDevice' }
    } catch {
        $pnputil = Join-Path $env:WINDIR 'System32\pnputil.exe'
        $flag = if ($Op -eq 'disable') { '/disable-device' } else { '/remove-device' }
        $out = & $pnputil $flag $InstanceId 2>&1 | Out-String
        return @{ Ok = ($LASTEXITCODE -eq 0); Text = $out.Trim(); Code = $LASTEXITCODE }
    }
}

$all = @(Get-PnpDevice -ErrorAction SilentlyContinue)
foreach ($rule in $targets) {
    $hits = @($all | Where-Object {
            -not (Test-KeepDevice $_.FriendlyName $_.InstanceId) -and (
                ($_.FriendlyName -and $_.FriendlyName -match $rule.Match) -or
                ($_.InstanceId -and $_.InstanceId -match $rule.Also)
            )
        })
    if (-not $hits.Count) {
        Write-Log ("No match: {0}" -f $rule.Match) 'DarkGray'
        continue
    }
    foreach ($dev in $hits) {
        Write-Log ("{0}  {1}  [{2}]  {3}" -f $rule.Action.ToUpper(), $dev.Status, $dev.FriendlyName, $dev.InstanceId) 'Yellow'
        $disable = Invoke-DeviceOp -Op disable -InstanceId $dev.InstanceId
        Write-Log ("  disable ok={0} {1}" -f $disable.Ok, $disable.Text) 'DarkGray'
        if ($rule.Action -eq 'remove') {
            $rm = Invoke-DeviceOp -Op remove -InstanceId $dev.InstanceId
            Write-Log ("  remove ok={0} {1}" -f $rm.Ok, $rm.Text) 'DarkGray'
        }
    }
}

# PAN miniport — do not start Bluetooth networking (tether) adapter
$bthPan = Get-Service -Name 'BthPan' -ErrorAction SilentlyContinue
if ($bthPan) {
    if ($bthPan.Status -ne 'Stopped') {
        Stop-Service -Name 'BthPan' -Force -ErrorAction SilentlyContinue
    }
    if ($bthPan.StartType -ne 'Disabled') {
        Set-Service -Name 'BthPan' -StartupType Disabled -ErrorAction SilentlyContinue
    }
    Write-Log 'BthPan service disabled (Bluetooth PAN networking off; Classic BT audio/HID stays)' 'Green'
}

# Sonic Studio / Nahimic leftovers
$nah = Get-Service -Name 'NahimicService' -ErrorAction SilentlyContinue
if ($nah) {
    Stop-Service -Name 'NahimicService' -Force -ErrorAction SilentlyContinue
    Set-Service -Name 'NahimicService' -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Log 'NahimicService stopped + disabled' 'Green'
}

Get-Process -Name 'asusns', 'NahimicSvc64', 'NahimicSvc32', 'NahimicService' -ErrorAction SilentlyContinue |
    ForEach-Object {
        Write-Log ("Stopping process {0} pid {1}" -f $_.Name, $_.Id) 'Yellow'
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }

foreach ($task in @(
        'NahimicTask32', 'NahimicTask64',
        'ArmourySocketServer', 'AcPowerNotification', 'Framework Service', 'P508PowerAgent_sdk'
    )) {
    $st = Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($st) {
        Disable-ScheduledTask -TaskName $st.TaskName -TaskPath $st.TaskPath -ErrorAction SilentlyContinue | Out-Null
        Write-Log ("Disabled task {0}{1}" -f $st.TaskPath, $st.TaskName) 'Green'
    }
}

# Owners we keep
foreach ($svcName in @('LConnectService', 'LConnectServiceWatcher')) {
    $s = Get-Service -Name $svcName -ErrorAction SilentlyContinue
    if ($s) { Write-Log ("KEEP service {0} Status={1} Start={2}" -f $s.Name, $s.Status, $s.StartType) 'Cyan' }
}

$bt500 = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -match 'USB-BT500' -and $_.Status -eq 'OK' }
if ($bt500) { Write-Log ('KEEP {0}' -f $bt500.FriendlyName) 'Cyan' }
else { Write-Log 'WARN: ASUS USB-BT500 not OK — Bluetooth comms may need a look' 'Red' }

if ($InstallGuard) {
    $scriptPath = Join-Path $ToolboxRoot 'Scripts\Set-FAFOConflictDevices.ps1'
    $ps = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""
    $action = New-ScheduledTaskAction -Execute $ps -Argument $arg
    $t1 = New-ScheduledTaskTrigger -AtStartup
    $t2 = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger @($t1, $t2) -Principal $principal -Settings $settings -Force | Out-Null
    Write-Log "Installed startup/logon task $TaskName" 'Green'
}

Write-Log '=== done ===' 'Cyan'
Write-Host "Log file: $logFile"
