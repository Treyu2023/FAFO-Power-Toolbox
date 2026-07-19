@{
    RootModule        = 'FAFO.Verifone.psm1'
    ModuleVersion     = '1.3.0'
    GUID              = 'e2f9a4b1-7c58-4d2e-9a01-3b6c8d5e4f70'
    Author            = 'FAFO Power Toolbox'
    CompanyName       = 'FAFO'
    Copyright         = '(c) FAFO. Local use only.'
    Description       = 'Verifone POS backup library, system health report, interactive PLU/dept exploration, scripted price edits, and rollback.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
        'Test-FAFOVerifoneBackup',
        'Import-FAFOVerifoneBackup',
        'Get-FAFOVerifoneBackup',
        'Get-FAFOVerifoneDemoBackupPath',
        'Get-FAFOVerifoneItem',
        'Get-FAFOVerifoneDepartment',
        'Get-FAFOVerifoneDepartmentSummary',
        'Get-FAFOVerifoneHealthReport',
        'Show-FAFOVerifoneHealthReport',
        'Show-FAFOVerifoneHealthFlag',
        'Show-FAFOVerifoneItem',
        'Show-FAFOVerifoneDepartment',
        'Invoke-FAFOVerifoneHealthExplorer',
        'Invoke-FAFOVerifoneExplorer',
        'Get-FAFOVerifonePriceChange',
        'Set-FAFOVerifoneItemPrice',
        'Set-FAFOVerifoneDepartmentPrice',
        'Set-FAFOVerifoneMassPrice',
        'Export-FAFOVerifonePriceChange',
        'Save-FAFOVerifoneBackup',
        'Export-FAFOVerifoneSnapshot',
        'Get-FAFOVerifoneLibraryShellPath',
        'Get-FAFOVerifoneLibraryRoot',
        'Set-FAFOVerifoneSitesRoot',
        'Initialize-FAFOVerifoneSitesLink',
        'Get-FAFOVerifoneSitePath',
        'Get-FAFOVerifoneLibrarySite',
        'Update-FAFOVerifoneLibraryIndex',
        'Show-FAFOVerifoneLibrary',
        'Add-FAFOVerifoneLibraryBackup',
        'Open-FAFOVerifoneLibrarySite',
        'Save-FAFOVerifoneWorkingCopy',
        'Get-FAFOVerifoneEditScript',
        'Save-FAFOVerifoneEditScript',
        'Restore-FAFOVerifoneEditScript',
        'Redo-FAFOVerifoneEditScript'
    )
    CmdletsToExport   = @()
    VariablesToExport = @()
    AliasesToExport   = @()
    PrivateData       = @{
        PSData = @{
            Tags = @('FAFO', 'Verifone', 'POS', 'PLU', 'Health', 'Backup', 'Library', 'Petro')
        }
    }
}
