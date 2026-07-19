@{
    RootModule        = 'FAFO.Secrets.psm1'
    ModuleVersion     = '1.0.0'
    GUID              = 'a7c3e91f-4b2d-4f18-9e6a-8d5c1b0f2a47'
    Author            = 'FAFO Power Toolbox'
    CompanyName       = 'FAFO'
    Copyright         = '(c) FAFO. Local use only.'
    Description       = 'DPAPI-backed secret store for FAFO Power Toolbox (CurrentUser scope).'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
        'Set-FAFOSecret',
        'Get-FAFOSecret',
        'Test-FAFOSecret',
        'Remove-FAFOSecret',
        'Set-FAFOSecretFromPlainText',
        'Initialize-FAFOEnvironment'
    )
    CmdletsToExport   = @()
    VariablesToExport = @()
    AliasesToExport   = @()
    PrivateData       = @{
        PSData = @{
            Tags = @('FAFO', 'Secrets', 'DPAPI', 'Security')
        }
    }
}
