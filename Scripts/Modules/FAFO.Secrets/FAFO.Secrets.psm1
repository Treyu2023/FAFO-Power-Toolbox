# FAFO.Secrets.psm1
# DPAPI-backed secret store for FAFO Power Toolbox (CurrentUser scope)

if (-not ('System.Security.Cryptography.ProtectedData' -as [type])) {
    Add-Type -AssemblyName System.Security.Cryptography.ProtectedData
}

$script:SecretDir = Join-Path $env:LOCALAPPDATA 'FAFO\Secrets'
if (-not (Test-Path $script:SecretDir)) {
    New-Item -Path $script:SecretDir -ItemType Directory -Force | Out-Null
}

function Set-FAFOSecret {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][SecureString]$SecureValue
    )

    $path = Join-Path $script:SecretDir "$Name.xml"

    $ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        $plainText = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($plainText)
        $encrypted = [System.Security.Cryptography.ProtectedData]::Protect(
            $bytes,
            $null,
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        [System.IO.File]::WriteAllBytes($path, $encrypted)
        Write-Host "Secret '$Name' stored securely (DPAPI)" -ForegroundColor Green
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    }
}

function Get-FAFOSecret {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)

    $path = Join-Path $script:SecretDir "$Name.xml"
    if (-not (Test-Path $path)) { return $null }

    try {
        $encrypted = [System.IO.File]::ReadAllBytes($path)
        $bytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
            $encrypted,
            $null,
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        return [System.Text.Encoding]::UTF8.GetString($bytes)
    }
    catch {
        Write-Warning "Failed to decrypt secret '$Name'"
        return $null
    }
}

function Test-FAFOSecret {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Name)

    $path = Join-Path $script:SecretDir "$Name.xml"
    return (Test-Path $path)
}

function Remove-FAFOSecret {
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)][string]$Name)

    $path = Join-Path $script:SecretDir "$Name.xml"
    if (-not (Test-Path $path)) {
        Write-Warning "Secret '$Name' not found"
        return
    }
    if ($PSCmdlet.ShouldProcess($Name, 'Remove FAFO secret')) {
        Remove-Item -Path $path -Force
        Write-Host "Secret '$Name' removed" -ForegroundColor Yellow
    }
}

function Set-FAFOSecretFromPlainText {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$PlainText
    )

    $secure = ConvertTo-SecureString $PlainText -AsPlainText -Force
    Set-FAFOSecret -Name $Name -SecureValue $secure
}

function Initialize-FAFOEnvironment {
    [CmdletBinding()]
    param(
        [string[]]$Names = @('XAI_API_KEY', 'ABUSE_CH_AUTH_KEY')
    )

    foreach ($name in $Names) {
        $value = Get-FAFOSecret -Name $name
        if ($value) {
            Set-Item -Path "env:$name" -Value $value
            Write-Host "Loaded $name into environment" -ForegroundColor Green
        }
        else {
            Write-Warning "$name not found in secret store"
        }
    }
}

Export-ModuleMember -Function @(
    'Set-FAFOSecret',
    'Get-FAFOSecret',
    'Test-FAFOSecret',
    'Remove-FAFOSecret',
    'Set-FAFOSecretFromPlainText',
    'Initialize-FAFOEnvironment'
)
