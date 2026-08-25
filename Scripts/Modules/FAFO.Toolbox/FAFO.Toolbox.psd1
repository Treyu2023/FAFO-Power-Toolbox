@{
    RootModule        = 'FAFO.Toolbox.psm1'
    ModuleVersion     = '1.4.2'
    GUID              = 'c4e8b12a-6f39-4d7e-a1c0-9b8e5f2d3a61'
    Author            = 'FAFO Power Toolbox'
    CompanyName       = 'FAFO'
    Copyright         = '(c) FAFO. Local use only.'
    Description       = 'Paths, logging, safe file ops, health, device profiles, connection tests, and report helpers for FAFO Power Toolbox.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
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
        'Write-FAFOLog',
        'Backup-FAFOItem',
        'Move-FAFOItem',
        'Copy-FAFOItem',
        'Move-FAFOHtmlEditBackups',
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
        'Open-FAFOPath',
        'Get-FAFODeviceProfile',
        'Select-FAFODeviceProfile',
        'Get-FAFOConnectionTest'
    )
    CmdletsToExport   = @()
    VariablesToExport = @()
    AliasesToExport   = @()
    PrivateData       = @{
        PSData = @{
            Tags = @('FAFO', 'Toolbox', 'Reports', 'Logging', 'Automation', 'Security', 'Petro', 'Connectivity')
        }
    }
}
