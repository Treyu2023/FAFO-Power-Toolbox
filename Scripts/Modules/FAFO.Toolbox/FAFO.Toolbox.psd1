@{
    RootModule        = 'FAFO.Toolbox.psm1'
    ModuleVersion     = '1.3.0'
    GUID              = 'c4e8b12a-6f39-4d7e-a1c0-9b8e5f2d3a61'
    Author            = 'FAFO Power Toolbox'
    CompanyName       = 'FAFO'
    Copyright         = '(c) FAFO. Local use only.'
    Description       = 'Paths, logging, safe file ops, health, and report helpers for FAFO Power Toolbox.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
        'Get-FAFOToolboxRoot',
        'Set-FAFOToolboxRoot',
        'Get-FAFODeviceId',
        'Get-FAFOCommonPaths',
        'Initialize-FAFOPaths',
        'Get-FAFOEnvironment',
        'Write-FAFOLog',
        'Backup-FAFOItem',
        'Move-FAFOItem',
        'Copy-FAFOItem',
        'Get-FAFOStatus',
        'Test-FAFOHealth',
        'Write-FAFOStatusReport',
        'Invoke-FAFOGrokDiag',
        'Invoke-FAFOSystemDiagnostics',
        'New-FAFOReportName',
        'Write-FAFOReport',
        'Get-FAFOReport',
        'Remove-FAFOReport',
        'Compress-FAFOReport',
        'Open-FAFOPath'
    )
    CmdletsToExport   = @()
    VariablesToExport = @()
    AliasesToExport   = @()
    PrivateData       = @{
        PSData = @{
            Tags = @('FAFO', 'Toolbox', 'Reports', 'Logging', 'Automation', 'Security')
        }
    }
}
