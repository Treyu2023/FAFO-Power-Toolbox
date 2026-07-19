# Collect BIOS / firmware / OS-visible system configuration for report
# Output is ALWAYS device-local — never a shared D:\ path that can leak into git.
$ErrorActionPreference = 'Continue'
$deviceId = ($env:COMPUTERNAME -replace '[^\w\.-]+', '-').ToUpperInvariant()
$outDir = Join-Path $env:LOCALAPPDATA "FAFO\Devices\$deviceId\Reports\PC"
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$raw = Join-Path $outDir 'bios_system_raw.json'
Write-Host "Device: $deviceId"
Write-Host "Output: $outDir"
$lines = New-Object System.Collections.Generic.List[string]
function A([string]$s) { [void]$lines.Add($s) }

$data = [ordered]@{}

# --- Identity ---
try {
  $cs = Get-CimInstance Win32_ComputerSystem
  $bb = Get-CimInstance Win32_BaseBoard
  $bios = Get-CimInstance Win32_BIOS
  $os = Get-CimInstance Win32_OperatingSystem
  $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
  $data.Machine = [ordered]@{
    ComputerName = $cs.Name
    Manufacturer = $cs.Manufacturer
    Model = $cs.Model
    SystemFamily = $cs.SystemFamily
    SystemSKU = $cs.SystemSKUNumber
    DomainRole = $cs.DomainRole
    HypervisorPresent = $cs.HypervisorPresent
    TotalRAM_GB = [math]::Round($cs.TotalPhysicalMemory/1GB, 2)
    BootupState = $cs.BootupState
  }
  $data.Motherboard = [ordered]@{
    Manufacturer = $bb.Manufacturer
    Product = $bb.Product
    Version = $bb.Version
    SerialNumber = $bb.SerialNumber
  }
  $data.BIOS = [ordered]@{
    Manufacturer = $bios.Manufacturer
    Name = $bios.Name
    SMBIOSBIOSVersion = $bios.SMBIOSBIOSVersion
    Version = ($bios.Version -join ' ')
    ReleaseDate = $bios.ReleaseDate
    SerialNumber = $bios.SerialNumber
    SMBIOSMajor = $bios.SMBIOSMajorVersion
    SMBIOSMinor = $bios.SMBIOSMinorVersion
    BIOSCharacteristics = $bios.BiosCharacteristics
  }
  $data.OS = [ordered]@{
    Caption = $os.Caption
    Version = $os.Version
    Build = $os.BuildNumber
    Architecture = $os.OSArchitecture
    InstallDate = $os.InstallDate
    LastBoot = $os.LastBootUpTime
    Locale = $os.Locale
  }
  $data.CPU = [ordered]@{
    Name = $cpu.Name
    Cores = $cpu.NumberOfCores
    Logical = $cpu.NumberOfLogicalProcessors
    MaxClockMHz = $cpu.MaxClockSpeed
    CurrentClockMHz = $cpu.CurrentClockSpeed
    L2 = $cpu.L2CacheSize
    L3 = $cpu.L3CacheSize
    VirtualizationFirmwareEnabled = $cpu.VirtualizationFirmwareEnabled
    VMMonitorModeExtensions = $cpu.VMMonitorModeExtensions
    SecondLevelAddressTranslation = $cpu.SecondLevelAddressTranslationExtensions
  }
} catch { A "Identity error: $_" }

# --- Secure Boot / UEFI ---
try {
  $sb = $null
  try { $sb = Confirm-SecureBootUEFI -ErrorAction Stop } catch { $sb = "Error: $($_.Exception.Message)" }
  $data.Firmware = [ordered]@{
    SecureBoot = $sb
    FirmwareType = $env:firmware_type
  }
  # Alternative
  try {
    $ft = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control' -Name PEFirmwareType -EA SilentlyContinue).PEFirmwareType
    # 1=BIOS 2=UEFI
    $data.Firmware.PEFirmwareType = $ft
    $data.Firmware.PEFirmwareTypeLabel = switch ($ft) { 1 {'Legacy BIOS'} 2 {'UEFI'} default {"Unknown ($ft)"} }
  } catch {}
} catch {}

# --- TPM ---
try {
  $tpm = Get-Tpm -ErrorAction SilentlyContinue
  if ($tpm) {
    $data.TPM = [ordered]@{
      TpmPresent = $tpm.TpmPresent
      TpmReady = $tpm.TpmReady
      TpmEnabled = $tpm.TpmEnabled
      TpmActivated = $tpm.TpmActivated
      TpmOwned = $tpm.TpmOwned
      ManufacturerVersion = $tpm.ManufacturerVersion
      ManufacturerIdTxt = $tpm.ManufacturerIdTxt
      SpecVersion = ($tpm.SpecVersion -join ', ')
    }
  } else {
    $data.TPM = @{ Error = 'Get-Tpm unavailable' }
  }
} catch { $data.TPM = @{ Error = "$_" } }

# --- Memory modules (XMP proxy: configured speed) ---
try {
  $mem = @(Get-CimInstance Win32_PhysicalMemory)
  $data.MemoryModules = @($mem | ForEach-Object {
    [ordered]@{
      Bank = $_.BankLabel
      DeviceLocator = $_.DeviceLocator
      Capacity_GB = [math]::Round($_.Capacity/1GB, 2)
      Speed_MHz = $_.Speed
      ConfiguredClockSpeed = $_.ConfiguredClockSpeed
      Manufacturer = $_.Manufacturer
      PartNumber = ($_.PartNumber -replace '\s+$','')
      FormFactor = $_.FormFactor
      SMBIOSMemoryType = $_.SMBIOSMemoryType
    }
  })
  $speeds = $mem | ForEach-Object { $_.ConfiguredClockSpeed } | Where-Object { $_ }
  $data.MemorySummary = [ordered]@{
    Modules = $mem.Count
    Total_GB = [math]::Round(($mem | Measure-Object Capacity -Sum).Sum/1GB, 2)
    ConfiguredSpeeds_MHz = ($speeds | Select-Object -Unique) -join ', '
    MaxSpeed_MHz = ($mem | ForEach-Object { $_.Speed } | Measure-Object -Maximum).Maximum
  }
} catch {}

# --- GPU ---
try {
  $data.GPUs = @(Get-CimInstance Win32_VideoController | ForEach-Object {
    [ordered]@{
      Name = $_.Name
      DriverVersion = $_.DriverVersion
      DriverDate = $_.DriverDate
      AdapterRAM_GB = if ($_.AdapterRAM -and $_.AdapterRAM -gt 0) { [math]::Round($_.AdapterRAM/1GB, 2) } else { $null }
      VideoMode = $_.VideoModeDescription
      Status = $_.Status
      PNPDeviceID = $_.PNPDeviceID
    }
  })
} catch {}

# --- Disks ---
try {
  $data.Disks = @(Get-PhysicalDisk | ForEach-Object {
    [ordered]@{
      FriendlyName = $_.FriendlyName
      MediaType = $_.MediaType
      BusType = $_.BusType
      Size_GB = [math]::Round($_.Size/1GB, 1)
      Health = $_.HealthStatus
      Operational = $_.OperationalStatus
    }
  })
} catch {}

# --- Network ---
try {
  $data.Network = @(Get-NetAdapter | Where-Object Status -eq 'Up' | ForEach-Object {
    [ordered]@{ Name = $_.Name; Desc = $_.InterfaceDescription; LinkSpeed = $_.LinkSpeed; Mac = $_.MacAddress }
  })
} catch {}

# --- Power / Sleep related (BIOS-adjacent) ---
try {
  $active = powercfg /GETACTIVESCHEME
  $data.Power = [ordered]@{ ActiveScheme = "$active" }
  # Hibernate / fast startup
  $hiber = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Power' -EA SilentlyContinue).HibernateEnabled
  $fast = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -EA SilentlyContinue).HiberbootEnabled
  $data.Power.HibernateEnabled = $hiber
  $data.Power.FastStartup_HiberbootEnabled = $fast
  # USB SS
  $data.Power.USB_SelectiveSuspend_Query = (powercfg /Q SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 | Out-String)
  $data.Power.ASPM_Query = (powercfg /Q SCHEME_CURRENT SUB_PCIEXPRESS ASPM | Out-String)
} catch {}

# --- Virtualization / Hyper-V features ---
try {
  $feat = @{}
  foreach ($f in @('Microsoft-Hyper-V-All','HypervisorPlatform','VirtualMachinePlatform','Windows-Hypervisor-Platform','Microsoft-Windows-Subsystem-Linux')) {
    try {
      $x = Get-WindowsOptionalFeature -Online -FeatureName $f -EA SilentlyContinue
      if ($x) { $feat[$f] = $x.State }
    } catch {}
  }
  $data.WindowsFeatures = $feat
} catch {}

# --- bcdedit (firmware boot) ---
try {
  $data.BCD = (bcdedit /enum {current} 2>&1 | Out-String)
} catch { $data.BCD = "$_" }

# --- USB power summary ---
try {
  $mp = @(Get-WmiObject -Namespace root\wmi -Class MSPower_DeviceEnable -EA SilentlyContinue)
  $usbOn = @($mp | Where-Object { $_.Enable -eq $true -and $_.InstanceName -match 'USB|ROOT_HUB|DEV_7A60|046D' })
  $usbOff = @($mp | Where-Object { $_.Enable -eq $false -and $_.InstanceName -match 'USB|ROOT_HUB|046D|174C|058F' })
  $data.USBPower = [ordered]@{
    TotalPowerObjects = $mp.Count
    USB_AllowPowerOff = $usbOn.Count
    USB_Protected = $usbOff.Count
    AllowList = @($usbOn | ForEach-Object { $_.InstanceName })
    DisableSelectiveSuspend = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\USB' -EA SilentlyContinue).DisableSelectiveSuspend
  }
} catch {}

# --- Device problems ---
try {
  $data.ProblemDevices = @(Get-PnpDevice -PresentOnly -EA SilentlyContinue |
    Where-Object { $_.Status -match 'Error|Degraded' } |
    ForEach-Object { [ordered]@{ Status=$_.Status; Class=$_.Class; Name=$_.FriendlyName; Id=$_.InstanceId } })
} catch {}

# --- BitLocker quick ---
try {
  $data.BitLocker = @(Get-BitLockerVolume -EA SilentlyContinue | ForEach-Object {
    [ordered]@{ MountPoint=$_.MountPoint; VolumeStatus=$_.VolumeStatus; ProtectionStatus=$_.ProtectionStatus; EncryptionPct=$_.EncryptionPercentage }
  })
} catch { $data.BitLocker = @() }

$data.CollectedAt = (Get-Date).ToString('o')
$data.Notes = $lines

$data | ConvertTo-Json -Depth 8 | Set-Content -Path $raw -Encoding UTF8
Write-Host "Wrote $raw"
# also print key summary
Write-Host "Board: $($data.Motherboard.Manufacturer) $($data.Motherboard.Product)"
Write-Host "BIOS: $($data.BIOS.SMBIOSBIOSVersion) $($data.BIOS.ReleaseDate)"
Write-Host "SecureBoot: $($data.Firmware.SecureBoot) Firmware: $($data.Firmware.PEFirmwareTypeLabel)"
Write-Host "TPM: present=$($data.TPM.TpmPresent) ready=$($data.TPM.TpmReady)"
Write-Host "VT: $($data.CPU.VirtualizationFirmwareEnabled) RAM: $($data.MemorySummary.ConfiguredSpeeds_MHz) MHz"
