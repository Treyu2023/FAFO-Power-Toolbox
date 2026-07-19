# FAFO.Verifone.psm1
# Verifone POS backup analysis, site library, scripted edits, health + explore
# Version: 1.2.0
#
# Design:
#   1) Detect/load backup XML sets into structured objects (PLU/Dept focused)
#   2) Site library: VerifoneLibrary\{MOC}\{Customer}\{Location}\
#        original\  = immutable first ingest (never edit)
#        working\   = current state after script replay
#        scripts\   = ordered edit scripts (not full tree copies)
#   3) Rollback = restore original + replay scripts 1..N (precise, cheap)
#   4) System Health Report (surface) → interactive drill-down (PLUs/Depts)
#   5) Pricing helpers + snapshot JSON for future HTML/Python UI

$script:FAFOVerifoneSession = $null

#region Internal helpers

function Write-FAFOVerifoneHost {
    param([string]$Message, [string]$Color = 'Cyan')
    Write-Host $Message -ForegroundColor $Color
}

function Get-FAFOVerifoneXmlField {
    param(
        [System.Xml.XmlElement]$Node,
        [string[]]$Names
    )
    if (-not $Node) { return $null }
    foreach ($n in $Names) {
        if ($Node.HasAttribute($n)) {
            $v = $Node.GetAttribute($n)
            if (-not [string]::IsNullOrWhiteSpace($v)) { return $v }
        }
    }
    foreach ($n in $Names) {
        $child = $Node[$n]
        if ($child -and -not [string]::IsNullOrWhiteSpace($child.InnerText)) {
            return $child.InnerText.Trim()
        }
    }
    # case-insensitive attribute scan
    foreach ($attr in $Node.Attributes) {
        foreach ($n in $Names) {
            if ($attr.Name -ieq $n -and -not [string]::IsNullOrWhiteSpace($attr.Value)) {
                return $attr.Value
            }
        }
    }
    return $null
}

function ConvertTo-FAFOVerifoneDecimal {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    $clean = $Value.Trim() -replace '[^\d\.\-]', ''
    if ([string]::IsNullOrWhiteSpace($clean)) { return $null }
    try {
        return [decimal]::Parse($clean, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        return $null
    }
}

function Resolve-FAFOVerifoneXmlRole {
    param(
        [string]$FileName,
        [System.Xml.XmlDocument]$Doc
    )
    $base = [System.IO.Path]::GetFileNameWithoutExtension($FileName).ToLowerInvariant()
    $root = if ($Doc.DocumentElement) { $Doc.DocumentElement.LocalName.ToLowerInvariant() } else { '' }

    if ($base -match 'plu|item|product|upc|sku' -or $root -match 'plu|item|product') { return 'Items' }
    if ($base -match 'dept|department' -or $root -match 'dept|department') { return 'Departments' }
    if ($base -match 'tax' -or $root -match 'tax') { return 'Taxes' }
    if ($base -match 'tender|paymedia|payment' -or $root -match 'tender|payment') { return 'Tenders' }
    if ($base -match 'config|store|site|system|terminal' -or $root -match 'config|store|site|system') { return 'Config' }
    if ($base -match 'fuel|grade|blend' -or $root -match 'fuel|grade') { return 'Fuel' }
    return 'Other'
}

function Get-FAFOVerifoneRecordNodes {
    param(
        [System.Xml.XmlDocument]$Doc,
        [string]$Role
    )
    if (-not $Doc -or -not $Doc.DocumentElement) { return @() }
    $root = $Doc.DocumentElement

    $candidateNames = switch ($Role) {
        'Items'       { @('Item', 'PLU', 'Product', 'PluItem', 'Merchandise') }
        'Departments' { @('Department', 'Dept', 'DeptRecord') }
        'Taxes'       { @('Tax', 'TaxRate', 'TaxGroup') }
        'Tenders'     { @('Tender', 'PayMedia', 'PaymentType') }
        'Fuel'        { @('Fuel', 'Grade', 'FuelGrade', 'Product') }
        default       { @() }
    }

    foreach ($name in $candidateNames) {
        $nodes = @($root.SelectNodes(".//*[local-name()='$name']"))
        if ($nodes.Count -gt 0) { return $nodes }
    }

    # Fallback: direct children that look like records (elements with attributes)
    $kids = @($root.ChildNodes | Where-Object { $_ -is [System.Xml.XmlElement] })
    if ($kids.Count -ge 1) {
        $withAttrs = @($kids | Where-Object { $_.Attributes.Count -gt 0 })
        if ($withAttrs.Count -gt 0) { return $withAttrs }
        return $kids
    }
    return @()
}

function Test-FAFOVerifoneFlagYes {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return $null }
    return [bool]($Value -match '^(Y|Yes|True|1|A|Active|T)$')
}

function ConvertFrom-FAFOVerifoneItemNode {
    param(
        [System.Xml.XmlElement]$Node,
        [string]$SourceFile
    )
    # SMS/Commander-style aliases — PLU identity separate from UPC when both exist
    $plu = Get-FAFOVerifoneXmlField $Node @('PLU', 'Plu', 'PluNumber', 'ItemCode', 'Code', 'Sku', 'Id', 'Number')
    $upc = Get-FAFOVerifoneXmlField $Node @('UPC', 'Upc', 'Barcode', 'ScanCode', 'EAN')
    if (-not $plu -and $upc) { $plu = $upc }
    $desc = Get-FAFOVerifoneXmlField $Node @('Description', 'Desc', 'Name', 'ItemName', 'LongDescription', 'ReceiptDesc')
    $dept = Get-FAFOVerifoneXmlField $Node @('DepartmentId', 'DeptId', 'Department', 'Dept', 'DeptCode', 'DepartmentCode', 'DepartmentNumber')
    $priceRaw = Get-FAFOVerifoneXmlField $Node @('Price', 'UnitPrice', 'Retail', 'Amount', 'SellPrice', 'CurrentPrice', 'Price1')
    $active = Get-FAFOVerifoneXmlField $Node @('Active', 'Enabled', 'Status', 'IsActive')
    $productCode = Get-FAFOVerifoneXmlField $Node @('ProductCode', 'ProdCode', 'PCode', 'NACS', 'NacsCode', 'MerchandiseCode')
    $taxable = Get-FAFOVerifoneXmlField $Node @('Taxable', 'TaxFlag', 'Tax', 'IsTaxable', 'Tax1')
    $discountable = Get-FAFOVerifoneXmlField $Node @('Discountable', 'AllowDiscount', 'IsDiscountable')
    $returnable = Get-FAFOVerifoneXmlField $Node @('Returnable', 'AllowReturn', 'IsReturnable')
    $mixMatch = Get-FAFOVerifoneXmlField $Node @('MixMatch', 'MixMatchCode', 'MMCode', 'MixAndMatch')
    $price = ConvertTo-FAFOVerifoneDecimal $priceRaw

    [PSCustomObject]@{
        PSTypeName    = 'FAFO.Verifone.Item'
        PLU           = $plu
        UPC           = $upc
        Description   = $desc
        DepartmentId  = $dept
        Price         = $price
        PriceRaw      = $priceRaw
        ProductCode   = $productCode
        Taxable       = $taxable
        Discountable  = $discountable
        Returnable    = $returnable
        MixMatch      = $mixMatch
        Active        = $active
        IsActive      = $(if ($null -eq (Test-FAFOVerifoneFlagYes $active)) { $true } else { Test-FAFOVerifoneFlagYes $active })
        SourceFile    = $SourceFile
        # Keep node for write-back
        _XmlNode      = $Node
    }
}

function ConvertFrom-FAFOVerifoneDeptNode {
    param(
        [System.Xml.XmlElement]$Node,
        [string]$SourceFile
    )
    [PSCustomObject]@{
        PSTypeName   = 'FAFO.Verifone.Department'
        Id           = Get-FAFOVerifoneXmlField $Node @('Id', 'DeptId', 'DepartmentId', 'Code', 'Number', 'DepartmentNumber')
        Name         = Get-FAFOVerifoneXmlField $Node @('Name', 'Description', 'DeptName', 'DepartmentName')
        TaxGroup     = Get-FAFOVerifoneXmlField $Node @('TaxGroup', 'TaxId', 'Tax', 'TaxCode')
        ProductCode  = Get-FAFOVerifoneXmlField $Node @('ProductCode', 'ProdCode', 'PCode', 'NACS', 'NacsCode')
        Category     = Get-FAFOVerifoneXmlField $Node @('Category', 'DeptCategory', 'Type', 'Class')
        MinPrice     = ConvertTo-FAFOVerifoneDecimal (Get-FAFOVerifoneXmlField $Node @('MinPrice', 'Minimum', 'Min', 'PriceMin'))
        MaxPrice     = ConvertTo-FAFOVerifoneDecimal (Get-FAFOVerifoneXmlField $Node @('MaxPrice', 'Maximum', 'Max', 'PriceMax'))
        SourceFile   = $SourceFile
        _XmlNode     = $Node
    }
}

function ConvertFrom-FAFOVerifoneTaxNode {
    param([System.Xml.XmlElement]$Node, [string]$SourceFile)
    [PSCustomObject]@{
        PSTypeName = 'FAFO.Verifone.Tax'
        Id         = Get-FAFOVerifoneXmlField $Node @('Id', 'TaxId', 'Code', 'Number')
        Name       = Get-FAFOVerifoneXmlField $Node @('Name', 'Description')
        Rate       = ConvertTo-FAFOVerifoneDecimal (Get-FAFOVerifoneXmlField $Node @('Rate', 'Percent', 'Percentage', 'TaxRate'))
        SourceFile = $SourceFile
    }
}

function ConvertFrom-FAFOVerifoneTenderNode {
    param([System.Xml.XmlElement]$Node, [string]$SourceFile)
    [PSCustomObject]@{
        PSTypeName = 'FAFO.Verifone.Tender'
        Id         = Get-FAFOVerifoneXmlField $Node @('Id', 'TenderId', 'Code', 'Number')
        Name       = Get-FAFOVerifoneXmlField $Node @('Name', 'Description')
        Type       = Get-FAFOVerifoneXmlField $Node @('Type', 'TenderType', 'MediaType')
        SourceFile = $SourceFile
    }
}

function Get-FAFOVerifoneStoreInfo {
    param([System.Collections.IDictionary]$XmlByRole)

    $info = [ordered]@{
        Name       = $null
        SiteId     = $null
        Version    = $null
        Address    = $null
        BackupDate = $null
        SourceHint = $null
        MOC        = $null
        Customer   = $null
        Location   = $null
    }

    $docs = @()
    if ($XmlByRole.Contains('Config')) { $docs += $XmlByRole['Config'] }
    foreach ($kv in $XmlByRole.GetEnumerator()) { $docs += $kv.Value }
    $docs = $docs | Select-Object -Unique

    foreach ($doc in $docs) {
        if (-not $doc -or -not $doc.DocumentElement) { continue }
        $el = $doc.DocumentElement
        # Prefer Store-like nodes
        $storeNode = $el.SelectSingleNode(".//*[local-name()='Store' or local-name()='Site' or local-name()='StoreConfig' or local-name()='Customer']")
        $sysNode = $el.SelectSingleNode(".//*[local-name()='System' or local-name()='Header' or local-name()='MOC']")
        foreach ($node in @($storeNode, $sysNode, $el)) {
            if (-not $node) { continue }
            if (-not $info.Name) { $info.Name = Get-FAFOVerifoneXmlField $node @('Name', 'StoreName', 'SiteName') }
            if (-not $info.SiteId) { $info.SiteId = Get-FAFOVerifoneXmlField $node @('SiteId', 'StoreId', 'Id', 'Number') }
            if (-not $info.Version) { $info.Version = Get-FAFOVerifoneXmlField $node @('Version', 'SoftwareVersion', 'AppVersion', 'Release') }
            if (-not $info.Address) { $info.Address = Get-FAFOVerifoneXmlField $node @('Address', 'Street') }
            if (-not $info.BackupDate) { $info.BackupDate = Get-FAFOVerifoneXmlField $node @('BackupDate', 'Date', 'Created', 'ExportDate') }
            if (-not $info.SourceHint) { $info.SourceHint = Get-FAFOVerifoneXmlField $node @('Source', 'Origin') }
            if (-not $info.MOC) {
                $info.MOC = Get-FAFOVerifoneXmlField $node @('MOC', 'Moc', 'Marketer', 'Chain', 'Brand', 'DealerGroup', 'OilCompany')
            }
            if (-not $info.Customer) {
                $info.Customer = Get-FAFOVerifoneXmlField $node @('Customer', 'CustomerName', 'Owner', 'Dealer', 'AccountName', 'Company')
            }
            if (-not $info.Location) {
                $info.Location = Get-FAFOVerifoneXmlField $node @('Location', 'LocationName', 'SiteLocation', 'StoreLocation', 'City')
            }
        }
    }

    # Sensible fallbacks for library pathing when fields are missing
    if (-not $info.MOC) { $info.MOC = 'Unknown-MOC' }
    if (-not $info.Customer) { $info.Customer = $(if ($info.Name) { $info.Name } else { 'Unknown-Customer' }) }
    if (-not $info.Location) {
        $info.Location = $(if ($info.Address) { $info.Address } elseif ($info.SiteId) { $info.SiteId } else { 'Unknown-Location' })
    }

    return [PSCustomObject]$info
}

function ConvertTo-FAFOSafeName {
    param([string]$Name, [string]$Fallback = 'Unknown')
    if ([string]::IsNullOrWhiteSpace($Name)) { $Name = $Fallback }
    $safe = $Name.Trim()
    foreach ($c in [System.IO.Path]::GetInvalidFileNameChars()) {
        $safe = $safe.Replace([string]$c, '-')
    }
    $safe = ($safe -replace '\s+', ' ').Trim()
    $safe = $safe -replace '[\[\]\{\}#]+', '-'
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = $Fallback }
    # Keep paths readable but bounded
    if ($safe.Length -gt 80) { $safe = $safe.Substring(0, 80).Trim() }
    return $safe
}

function Set-FAFOVerifoneNodePrice {
    param(
        [System.Xml.XmlElement]$Node,
        [decimal]$NewPrice
    )
    if (-not $Node) { return $false }
    $formatted = ('{0:0.####}' -f $NewPrice).TrimEnd('0').TrimEnd('.')
    if ($formatted -eq '' -or $formatted -eq '-') { $formatted = '0' }

    foreach ($attrName in @('Price', 'UnitPrice', 'Retail', 'Amount', 'SellPrice', 'CurrentPrice')) {
        if ($Node.HasAttribute($attrName)) {
            $Node.SetAttribute($attrName, $formatted)
            return $true
        }
    }
    foreach ($attr in $Node.Attributes) {
        if ($attr.Name -match '(?i)price|retail') {
            $attr.Value = $formatted
            return $true
        }
    }
    $priceChild = $Node['Price']
    if ($priceChild) {
        $priceChild.InnerText = $formatted
        return $true
    }
    # Create Price attribute as last resort
    $Node.SetAttribute('Price', $formatted)
    return $true
}

function Assert-FAFOVerifoneSession {
    if (-not $script:FAFOVerifoneSession) {
        throw 'No Verifone backup loaded. Run Import-FAFOVerifoneBackup -Path <folder> first.'
    }
    return $script:FAFOVerifoneSession
}

#endregion

#region Detect / Import

function Test-FAFOVerifoneBackup {
    <#
    .SYNOPSIS
      Detect whether a folder looks like a Verifone-style XML backup collection.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [PSCustomObject]@{
            IsBackup   = $false
            Path       = $Path
            XmlCount   = 0
            RolesFound = @()
            Confidence = 'None'
            Notes      = 'Path is not a folder'
        }
    }

    $xmlFiles = @(Get-ChildItem -LiteralPath $Path -Filter *.xml -File -Recurse -ErrorAction SilentlyContinue)
    $roles = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $parseOk = 0

    foreach ($f in $xmlFiles) {
        try {
            $doc = [xml](Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop)
            $role = Resolve-FAFOVerifoneXmlRole -FileName $f.Name -Doc $doc
            [void]$roles.Add($role)
            $parseOk++
        }
        catch { }
    }

    $roleList = @($roles)
    $score = 0
    if ($xmlFiles.Count -ge 1) { $score += 1 }
    if ($xmlFiles.Count -ge 3) { $score += 1 }
    if ($roleList -contains 'Items') { $score += 2 }
    if ($roleList -contains 'Departments') { $score += 1 }
    if ($roleList -contains 'Config' -or $roleList -contains 'Taxes' -or $roleList -contains 'Tenders') { $score += 1 }

    $confidence = switch ($score) {
        { $_ -ge 4 } { 'High'; break }
        { $_ -ge 2 } { 'Medium'; break }
        { $_ -ge 1 } { 'Low'; break }
        default { 'None' }
    }

    [PSCustomObject]@{
        IsBackup   = ($score -ge 2)
        Path       = (Resolve-Path -LiteralPath $Path).Path
        XmlCount   = $xmlFiles.Count
        ParsedOk   = $parseOk
        RolesFound = $roleList
        Confidence = $confidence
        Notes      = if ($score -ge 2) { 'Looks like a Verifone-style XML backup set' } else { 'Insufficient XML/role signals' }
    }
}

function Import-FAFOVerifoneBackup {
    <#
    .SYNOPSIS
      Load a Verifone backup folder into a structured in-memory session.
    .EXAMPLE
      Import-FAFOVerifoneBackup -Path 'D:\SiteBackups\Store12'
      Import-FAFOVerifoneBackup -Path (Join-Path (Split-Path (Get-Module FAFO.Verifone).Path) 'Samples\DemoBackup')
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Backup path not found: $Path"
    }

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $detect = Test-FAFOVerifoneBackup -Path $resolved
    if (-not $detect.IsBackup) {
        Write-Warning "Low confidence that this is a Verifone backup (Confidence=$($detect.Confidence)). Loading XML files anyway."
    }

    $xmlFiles = @(Get-ChildItem -LiteralPath $resolved -Filter *.xml -File -Recurse -ErrorAction SilentlyContinue)
    $fileMeta = [System.Collections.Generic.List[object]]::new()
    $xmlByPath = @{}
    $xmlByRole = @{}  # role -> list of docs; also first-wins map for role key

    $items = [System.Collections.Generic.List[object]]::new()
    $depts = [System.Collections.Generic.List[object]]::new()
    $taxes = [System.Collections.Generic.List[object]]::new()
    $tenders = [System.Collections.Generic.List[object]]::new()
    $fuel = [System.Collections.Generic.List[object]]::new()
    $otherFiles = [System.Collections.Generic.List[string]]::new()

    foreach ($f in $xmlFiles) {
        try {
            $raw = Get-Content -LiteralPath $f.FullName -Raw -ErrorAction Stop
            $doc = [xml]$raw
        }
        catch {
            $fileMeta.Add([PSCustomObject]@{
                    Name = $f.Name; FullPath = $f.FullName; Role = 'Unreadable'; RecordCount = 0; Error = $_.Exception.Message
                }) | Out-Null
            continue
        }

        $role = Resolve-FAFOVerifoneXmlRole -FileName $f.Name -Doc $doc
        $xmlByPath[$f.FullName] = $doc
        if (-not $xmlByRole.ContainsKey($role)) { $xmlByRole[$role] = [System.Collections.Generic.List[object]]::new() }
        $xmlByRole[$role].Add($doc) | Out-Null

        $nodes = Get-FAFOVerifoneRecordNodes -Doc $doc -Role $role
        $count = 0

        switch ($role) {
            'Items' {
                foreach ($n in $nodes) {
                    $items.Add((ConvertFrom-FAFOVerifoneItemNode -Node $n -SourceFile $f.Name)) | Out-Null
                    $count++
                }
            }
            'Departments' {
                foreach ($n in $nodes) {
                    $depts.Add((ConvertFrom-FAFOVerifoneDeptNode -Node $n -SourceFile $f.Name)) | Out-Null
                    $count++
                }
            }
            'Taxes' {
                foreach ($n in $nodes) {
                    $taxes.Add((ConvertFrom-FAFOVerifoneTaxNode -Node $n -SourceFile $f.Name)) | Out-Null
                    $count++
                }
            }
            'Tenders' {
                foreach ($n in $nodes) {
                    $tenders.Add((ConvertFrom-FAFOVerifoneTenderNode -Node $n -SourceFile $f.Name)) | Out-Null
                    $count++
                }
            }
            'Fuel' {
                foreach ($n in $nodes) {
                    # Treat fuel grades like light items for price tooling
                    $fuel.Add((ConvertFrom-FAFOVerifoneItemNode -Node $n -SourceFile $f.Name)) | Out-Null
                    $count++
                }
            }
            default {
                $otherFiles.Add($f.Name) | Out-Null
                $count = @($nodes).Count
            }
        }

        $fileMeta.Add([PSCustomObject]@{
                Name        = $f.Name
                FullPath    = $f.FullName
                Role        = $role
                RecordCount = $count
                Error       = $null
            }) | Out-Null
    }

    # Role -> primary doc map for store info
    $primaryByRole = @{}
    foreach ($k in $xmlByRole.Keys) {
        $primaryByRole[$k] = $xmlByRole[$k][0]
    }
    $store = Get-FAFOVerifoneStoreInfo -XmlByRole $primaryByRole

    $session = [PSCustomObject]@{
        PSTypeName     = 'FAFO.Verifone.BackupSession'
        RootPath       = $resolved
        Detected       = $detect
        LoadedAt       = Get-Date
        Store          = $store
        Files          = @($fileMeta)
        Departments    = @($depts)
        Items          = @($items)
        Fuel           = @($fuel)
        Taxes          = @($taxes)
        Tenders        = @($tenders)
        OtherXmlFiles  = @($otherFiles)
        XmlByPath      = $xmlByPath
        PriceChanges   = [System.Collections.Generic.List[object]]::new()
        IsDirty        = $false
        Library        = $null  # set by library open/ingest
    }

    $script:FAFOVerifoneSession = $session

    Write-FAFOVerifoneHost ("Loaded Verifone backup: {0}" -f $resolved) 'Green'
    Write-FAFOVerifoneHost ("  MOC={0} | Customer={1} | Location={2}" -f $store.MOC, $store.Customer, $store.Location) 'Gray'
    Write-FAFOVerifoneHost ("  Items={0}  Depts={1}  Taxes={2}  Tenders={3}  XML files={4}" -f `
            $items.Count, $depts.Count, $taxes.Count, $tenders.Count, $xmlFiles.Count) 'Gray'

    return $session
}

function Get-FAFOVerifoneBackup {
    <#
    .SYNOPSIS
      Return the currently loaded Verifone backup session (or null).
    #>
    [CmdletBinding()]
    param()
    return $script:FAFOVerifoneSession
}

function Get-FAFOVerifoneDemoBackupPath {
    <#
    .SYNOPSIS
      Path to the built-in synthetic demo backup (for training / dry-runs).
    #>
    [CmdletBinding()]
    param()
    $mod = $MyInvocation.MyCommand.Module
    $base = if ($mod -and $mod.ModuleBase) { $mod.ModuleBase } else { $PSScriptRoot }
    Join-Path $base 'Samples\DemoBackup'
}

#endregion

#region Query / Health / Explore

function Get-FAFOVerifoneDepartmentSummary {
    <#
    .SYNOPSIS
      Departments enriched with item counts (for health + drill-down).
    #>
    [CmdletBinding()]
    param()
    $s = Assert-FAFOVerifoneSession
    $items = @($s.Items)
    $counts = @{}
    foreach ($i in $items) {
        $key = [string]$i.DepartmentId
        if (-not $counts.ContainsKey($key)) { $counts[$key] = 0 }
        $counts[$key]++
    }

    $rows = foreach ($d in @($s.Departments)) {
        $id = [string]$d.Id
        $n = if ($counts.ContainsKey($id)) { $counts[$id] } else { 0 }
        [PSCustomObject]@{
            Id          = $d.Id
            Name        = $d.Name
            TaxGroup    = $d.TaxGroup
            ProductCode = $d.ProductCode
            Category    = $d.Category
            MinPrice    = $d.MinPrice
            MaxPrice    = $d.MaxPrice
            ItemCount   = $n
            IsEmpty     = ($n -eq 0)
            IsOrphan    = $false
            SourceFile  = $d.SourceFile
        }
    }

    # Orphan departments referenced by items but missing from department file
    $known = @($s.Departments | ForEach-Object { [string]$_.Id })
    $orphanIds = @($counts.Keys | Where-Object { $_ -and ($known -notcontains $_) })
    foreach ($oid in $orphanIds) {
        $rows += [PSCustomObject]@{
            Id          = $oid
            Name        = '(missing department record)'
            TaxGroup    = $null
            ProductCode = $null
            Category    = $null
            MinPrice    = $null
            MaxPrice    = $null
            ItemCount   = $counts[$oid]
            IsEmpty     = $false
            IsOrphan    = $true
            SourceFile  = $null
        }
    }

    $rows | Sort-Object { [int]($_.ItemCount) } -Descending
}

function Get-FAFOVerifoneItem {
    <#
    .SYNOPSIS
      Query loaded PLUs with field-tech filters.
    .EXAMPLE
      Get-FAFOVerifoneItem -Description '*COKE*'
      Get-FAFOVerifoneItem -DepartmentId 2 -MinPrice 5
      Get-FAFOVerifoneItem -ZeroPrice
      Get-FAFOVerifoneItem -MissingProductCode
    #>
    [CmdletBinding()]
    param(
        [string]$PLU,
        [string]$UPC,
        [string]$DepartmentId,
        [string]$Description,
        [string]$ProductCode,
        [nullable[decimal]]$MinPrice,
        [nullable[decimal]]$MaxPrice,
        [switch]$ActiveOnly,
        [switch]$InactiveOnly,
        [switch]$ZeroPrice,
        [switch]$MissingPrice,
        [switch]$MissingProductCode,
        [switch]$MissingUPC,
        [switch]$OrphanDepartment
    )
    $s = Assert-FAFOVerifoneSession
    $deptIds = @($s.Departments | ForEach-Object { [string]$_.Id })
    $q = @($s.Items)

    if ($PLU) { $q = $q | Where-Object { $_.PLU -like $PLU } }
    if ($UPC) { $q = $q | Where-Object { $_.UPC -like $UPC } }
    if ($DepartmentId) {
        $q = $q | Where-Object { [string]$_.DepartmentId -eq $DepartmentId -or $_.DepartmentId -like $DepartmentId }
    }
    if ($Description) { $q = $q | Where-Object { $_.Description -like "*$Description*" } }
    if ($ProductCode) { $q = $q | Where-Object { $_.ProductCode -like $ProductCode } }
    if ($PSBoundParameters.ContainsKey('MinPrice') -and $null -ne $MinPrice) {
        $q = $q | Where-Object { $null -ne $_.Price -and [decimal]$_.Price -ge $MinPrice }
    }
    if ($PSBoundParameters.ContainsKey('MaxPrice') -and $null -ne $MaxPrice) {
        $q = $q | Where-Object { $null -ne $_.Price -and [decimal]$_.Price -le $MaxPrice }
    }
    if ($ActiveOnly) { $q = $q | Where-Object { $_.IsActive } }
    if ($InactiveOnly) { $q = $q | Where-Object { -not $_.IsActive } }
    if ($ZeroPrice) { $q = $q | Where-Object { $null -ne $_.Price -and [decimal]$_.Price -eq 0 } }
    if ($MissingPrice) { $q = $q | Where-Object { $null -eq $_.Price } }
    if ($MissingProductCode) { $q = $q | Where-Object { [string]::IsNullOrWhiteSpace($_.ProductCode) } }
    if ($MissingUPC) { $q = $q | Where-Object { [string]::IsNullOrWhiteSpace($_.UPC) } }
    if ($OrphanDepartment) {
        $q = $q | Where-Object {
            $did = [string]$_.DepartmentId
            $did -and ($deptIds -notcontains $did)
        }
    }
    $q
}

function Get-FAFOVerifoneDepartment {
    <#
    .SYNOPSIS
      Query departments; use -WithCounts for item totals / empty detection.
    #>
    [CmdletBinding()]
    param(
        [string]$Id,
        [string]$Name,
        [string]$Category,
        [switch]$WithCounts,
        [switch]$EmptyOnly
    )
    if ($WithCounts -or $EmptyOnly) {
        $q = @(Get-FAFOVerifoneDepartmentSummary)
    }
    else {
        $s = Assert-FAFOVerifoneSession
        $q = @($s.Departments)
    }
    if ($Id) { $q = $q | Where-Object { [string]$_.Id -eq $Id -or $_.Id -like $Id } }
    if ($Name) { $q = $q | Where-Object { $_.Name -like "*$Name*" } }
    if ($Category) { $q = $q | Where-Object { $_.Category -like $Category } }
    if ($EmptyOnly) { $q = $q | Where-Object { $_.IsEmpty } }
    $q
}

function Get-FAFOVerifoneHealthReport {
    <#
    .SYNOPSIS
      System Health Report for the loaded working copy / library site.
    .DESCRIPTION
      Surface-first report: site identity, counts, pricing stats, and health flags
      (zero-price, missing product codes, empty depts, orphan depts, etc.).
      Flag samples support interactive drill-down via Show-FAFOVerifoneHealthFlag.
    #>
    [CmdletBinding()]
    param()

    $s = Assert-FAFOVerifoneSession
    $items = @($s.Items)
    $depts = @($s.Departments)
    $deptSummary = @(Get-FAFOVerifoneDepartmentSummary)
    $deptIds = @($depts | ForEach-Object { [string]$_.Id })

    $active = @($items | Where-Object { $_.IsActive })
    $inactive = @($items | Where-Object { -not $_.IsActive })
    $withPrice = @($items | Where-Object { $null -ne $_.Price })
    $zeroPrice = @($withPrice | Where-Object { [decimal]$_.Price -eq 0 })
    $noPrice = @($items | Where-Object { $null -eq $_.Price })
    $missingPcode = @($items | Where-Object { [string]::IsNullOrWhiteSpace($_.ProductCode) })
    $missingUpc = @($items | Where-Object { [string]::IsNullOrWhiteSpace($_.UPC) })
    $missingDesc = @($items | Where-Object { [string]::IsNullOrWhiteSpace($_.Description) })
    $orphanItems = @($items | Where-Object {
            $did = [string]$_.DepartmentId
            $did -and ($deptIds -notcontains $did)
        })
    $emptyDepts = @($deptSummary | Where-Object { $_.IsEmpty -and -not $_.IsOrphan })
    $orphanDepts = @($deptSummary | Where-Object { $_.IsOrphan })
    $dupPlus = @($items | Where-Object { $_.PLU } | Group-Object PLU | Where-Object { $_.Count -gt 1 })

    $priceStats = $null
    if ($withPrice.Count -gt 0) {
        $vals = @($withPrice | ForEach-Object { [decimal]$_.Price })
        $priceStats = [PSCustomObject]@{
            Min   = ($vals | Measure-Object -Minimum).Minimum
            Max   = ($vals | Measure-Object -Maximum).Maximum
            Avg   = [math]::Round((($vals | Measure-Object -Average).Average), 4)
            Count = $vals.Count
        }
    }

    $scriptLog = $null
    if ($s.Library -and $s.Library.ScriptsPath) {
        $scriptLog = Read-FAFOVerifoneScriptLog -ScriptsPath $s.Library.ScriptsPath
    }

    $flagList = [System.Collections.Generic.List[object]]::new()
    $flagDefs = @(
        @{ Id = 'ZeroPrice'; Severity = 'Warning'; Title = 'Zero-price PLUs'; Count = $zeroPrice.Count; Sample = $zeroPrice; Hint = 'Review free/test items or pricing errors' }
        @{ Id = 'MissingPrice'; Severity = 'Critical'; Title = 'PLUs missing parseable price'; Count = $noPrice.Count; Sample = $noPrice; Hint = 'Check Price/Retail field mapping for this backup layout' }
        @{ Id = 'MissingProductCode'; Severity = 'Warning'; Title = 'PLUs missing Product Code'; Count = $missingPcode.Count; Sample = $missingPcode; Hint = 'Product Code used for reporting/fuel/category links' }
        @{ Id = 'MissingUPC'; Severity = 'Info'; Title = 'PLUs missing UPC/barcode'; Count = $missingUpc.Count; Sample = $missingUpc; Hint = 'May be intentional for open depts/fuel keys' }
        @{ Id = 'MissingDescription'; Severity = 'Warning'; Title = 'PLUs missing description'; Count = $missingDesc.Count; Sample = $missingDesc; Hint = 'Hard to sell/identify at POS' }
        @{ Id = 'EmptyDepartment'; Severity = 'Warning'; Title = 'Empty departments (0 items)'; Count = $emptyDepts.Count; Sample = $emptyDepts; Hint = 'Unused dept or incomplete PLU file' }
        @{ Id = 'OrphanDepartment'; Severity = 'Critical'; Title = 'Items reference missing department'; Count = $orphanItems.Count; Sample = $orphanItems; Hint = 'Dept number on PLU not found in department file' }
        @{ Id = 'InactiveItems'; Severity = 'Info'; Title = 'Inactive PLUs'; Count = $inactive.Count; Sample = $inactive; Hint = 'Disabled items still in backup' }
        @{
            Id       = 'DuplicatePLU'
            Severity = 'Critical'
            Title    = 'Duplicate PLU codes'
            Count    = $dupPlus.Count
            Sample   = @($dupPlus | ForEach-Object { [PSCustomObject]@{ PLU = $_.Name; Count = $_.Count } })
            Hint     = 'Duplicate PLUs can cause unpredictable POS behavior'
        }
    )
    if ($items.Count -eq 0) {
        $flagDefs += @{
            Id = 'NoItems'; Severity = 'Critical'; Title = 'No PLU/items detected'; Count = 1
            Sample = @([PSCustomObject]@{ Note = 'Check file names / XML roles' })
            Hint = 'Backup may use nonstandard PLU file names'
        }
    }
    if (-not $s.Store.Name -and -not $s.Store.SiteId) {
        $flagDefs += @{
            Id = 'NoIdentity'; Severity = 'Warning'; Title = 'Store identity incomplete'; Count = 1
            Sample = @([PSCustomObject]@{ Note = 'Name/SiteId not found in config XML' })
            Hint = 'Library pathing may fall back to Unknown-*'
        }
    }
    foreach ($fd in $flagDefs) {
        if ([int]$fd.Count -le 0) { continue }
        $flagList.Add([PSCustomObject]@{
                Id       = $fd.Id
                Severity = $fd.Severity
                Title    = $fd.Title
                Count    = [int]$fd.Count
                Sample   = @($fd.Sample | Select-Object -First 25)
                Hint     = $fd.Hint
            }) | Out-Null
    }

    $critical = @($flagList | Where-Object Severity -eq 'Critical').Count
    $warnings = @($flagList | Where-Object Severity -eq 'Warning').Count
    $overall = if ($critical -gt 0) { 'Attention' } elseif ($warnings -gt 0) { 'Review' } else { 'Healthy' }

    [PSCustomObject]@{
        PSTypeName     = 'FAFO.Verifone.HealthReport'
        GeneratedAt    = Get-Date
        OverallStatus  = $overall
        BackupPath     = $s.RootPath
        LibraryPath    = if ($s.Library) { $s.Library.SitePath } else { $null }
        Detection      = $s.Detected
        Store          = $s.Store
        ScriptStatus   = if ($scriptLog) {
            [PSCustomObject]@{
                AppliedThrough = [int]$scriptLog.AppliedThrough
                ScriptCount    = @($scriptLog.Scripts).Count
            }
        }
        else { $null }
        Counts         = [PSCustomObject]@{
            XmlFiles          = @($s.Files).Count
            PLUs              = $items.Count
            ActivePLUs        = $active.Count
            InactivePLUs      = $inactive.Count
            Departments       = $depts.Count
            EmptyDepartments  = $emptyDepts.Count
            Taxes             = @($s.Taxes).Count
            Tenders           = @($s.Tenders).Count
            FuelRecords       = @($s.Fuel).Count
            PendingPriceEdits = $s.PriceChanges.Count
        }
        Pricing        = [PSCustomObject]@{
            ItemsWithPrice    = $withPrice.Count
            ItemsMissingPrice = $noPrice.Count
            ZeroPriceItems    = $zeroPrice.Count
            Stats             = $priceStats
        }
        Flags          = @($flagList | Sort-Object {
                switch ($_.Severity) { 'Critical' { 0 } 'Warning' { 1 } default { 2 } }
            }, { -1 * $_.Count })
        TopDepartments = @($deptSummary | Where-Object { -not $_.IsOrphan } | Select-Object -First 12 Id, Name, ItemCount, Category, ProductCode)
        DepartmentSummary = $deptSummary
        Files          = $s.Files
        IsDirty        = $s.IsDirty
        # Drill helpers (object refs for interactive layer)
        Drill          = [PSCustomObject]@{
            ZeroPriceItems      = $zeroPrice
            MissingPriceItems   = $noPrice
            MissingProductCodes = $missingPcode
            MissingUPCs         = $missingUpc
            OrphanItems         = $orphanItems
            EmptyDepartments    = $emptyDepts
            InactiveItems       = $inactive
        }
    }
}

function Show-FAFOVerifoneHealthReport {
    <#
    .SYNOPSIS
      Print surface System Health Report; optional Markdown export; optional interactive drill menu.
    .EXAMPLE
      Show-FAFOVerifoneHealthReport
      Show-FAFOVerifoneHealthReport -WriteReport -Interactive
    #>
    [CmdletBinding()]
    param(
        [switch]$WriteReport,
        [switch]$Interactive
    )

    $h = Get-FAFOVerifoneHealthReport
    $s = $h.Store
    $statusColor = switch ($h.OverallStatus) {
        'Healthy' { 'Green' }
        'Review'  { 'Yellow' }
        default   { 'Red' }
    }

    Write-Host ''
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host ' VERIFONE SYSTEM HEALTH REPORT (surface)' -ForegroundColor Cyan
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host ("Status:   {0}" -f $h.OverallStatus) -ForegroundColor $statusColor
    Write-Host ("Path:     {0}" -f $h.BackupPath)
    if ($h.LibraryPath) {
        Write-Host ("Library:  {0}" -f $h.LibraryPath) -ForegroundColor DarkCyan
    }
    Write-Host ''
    Write-Host 'Site identity' -ForegroundColor Yellow
    Write-Host ("  Store:    {0}" -f ($(if ($s.Name) { $s.Name } else { '(unknown)' })))
    Write-Host ("  Site ID:  {0}" -f ($(if ($s.SiteId) { $s.SiteId } else { '(unknown)' })))
    Write-Host ("  MOC:      {0}" -f $s.MOC)
    Write-Host ("  Customer: {0}" -f $s.Customer)
    Write-Host ("  Location: {0}" -f $s.Location)
    Write-Host ("  Version:  {0}" -f ($(if ($s.Version) { $s.Version } else { '(unknown)' })))
    Write-Host ("  Backup:   {0}" -f ($(if ($s.BackupDate) { $s.BackupDate } else { '(unknown)' })))
    Write-Host ("  Detect:   {0}  xml={1}" -f $h.Detection.Confidence, $h.Detection.XmlCount)
    if ($h.ScriptStatus) {
        Write-Host ("  Scripts:  applied through #{0} of {1}" -f $h.ScriptStatus.AppliedThrough, $h.ScriptStatus.ScriptCount)
    }

    Write-Host ''
    Write-Host 'Counts' -ForegroundColor Yellow
    Write-Host ("  PLUs: {0}  (active {1} / inactive {2})" -f $h.Counts.PLUs, $h.Counts.ActivePLUs, $h.Counts.InactivePLUs)
    Write-Host ("  Departments: {0}  (empty {1})" -f $h.Counts.Departments, $h.Counts.EmptyDepartments)
    Write-Host ("  Taxes: {0}   Tenders: {1}   Fuel: {2}   XML files: {3}" -f `
            $h.Counts.Taxes, $h.Counts.Tenders, $h.Counts.FuelRecords, $h.Counts.XmlFiles)
    Write-Host ("  Pending price edits (unsaved script): {0}" -f $h.Counts.PendingPriceEdits)

    Write-Host ''
    Write-Host 'Pricing snapshot' -ForegroundColor Yellow
    Write-Host ("  With price: {0}   Missing: {1}   Zero: {2}" -f `
            $h.Pricing.ItemsWithPrice, $h.Pricing.ItemsMissingPrice, $h.Pricing.ZeroPriceItems)
    if ($h.Pricing.Stats) {
        Write-Host ("  Min: {0}   Max: {1}   Avg: {2}" -f $h.Pricing.Stats.Min, $h.Pricing.Stats.Max, $h.Pricing.Stats.Avg)
    }

    if ($h.TopDepartments.Count) {
        Write-Host ''
        Write-Host 'Top departments by item count' -ForegroundColor Yellow
        $h.TopDepartments | Format-Table Id, Name, ItemCount, Category, ProductCode -AutoSize | Out-String | Write-Host
    }

    Write-Host 'Health flags' -ForegroundColor Yellow
    if ($h.Flags.Count -eq 0) {
        Write-Host '  (none) — looking clean' -ForegroundColor Green
    }
    else {
        $i = 1
        foreach ($f in $h.Flags) {
            $col = switch ($f.Severity) { 'Critical' { 'Red' } 'Warning' { 'Yellow' } default { 'Gray' } }
            Write-Host ("  [{0}] {1,-8} {2}  (count={3})" -f $i, $f.Severity, $f.Title, $f.Count) -ForegroundColor $col
            Write-Host ("       -> {0}" -f $f.Hint) -ForegroundColor DarkGray
            $i++
        }
        Write-Host ''
        Write-Host 'Drill-down: Show-FAFOVerifoneHealthFlag -Id ZeroPrice | Show-FAFOVerifoneItem -ZeroPrice' -ForegroundColor DarkGray
        Write-Host '           Invoke-FAFOVerifoneHealthExplorer  (guided menu)' -ForegroundColor DarkGray
    }
    Write-Host ''

    if ($WriteReport -and (Get-Command Write-FAFOReport -ErrorAction SilentlyContinue)) {
        $flagLines = ($h.Flags | ForEach-Object { "| $($_.Severity) | $($_.Title) | $($_.Count) | $($_.Hint) |" }) -join "`n"
        if (-not $flagLines) { $flagLines = '| OK | No flags | 0 | |' }
        $md = @"
# Verifone System Health Report
**Generated**: $($h.GeneratedAt.ToString('yyyy-MM-dd HH:mm:ss'))
**Status**: $($h.OverallStatus)
**Working path**: ``$($h.BackupPath)``
**Library**: ``$($h.LibraryPath)``

## Site
| Field | Value |
|-------|-------|
| Name | $($s.Name) |
| SiteId | $($s.SiteId) |
| MOC | $($s.MOC) |
| Customer | $($s.Customer) |
| Location | $($s.Location) |
| Version | $($s.Version) |

## Counts
| Metric | Value |
|--------|-------|
| PLUs | $($h.Counts.PLUs) |
| Active | $($h.Counts.ActivePLUs) |
| Departments | $($h.Counts.Departments) |
| Empty depts | $($h.Counts.EmptyDepartments) |
| Taxes | $($h.Counts.Taxes) |
| Tenders | $($h.Counts.Tenders) |

## Flags
| Severity | Title | Count | Hint |
|----------|-------|------:|------|
$flagLines
"@
        # Avoid serializing huge sample graphs into report raw if needed — full object is fine for now
        $raw = $h | Select-Object OverallStatus, GeneratedAt, BackupPath, LibraryPath, Store, Counts, Pricing, Flags, TopDepartments, ScriptStatus, IsDirty
        Write-FAFOReport -Name 'Verifone-Health' -Content $md -RawObject $raw | Out-Null
    }

    if ($Interactive) {
        Invoke-FAFOVerifoneHealthExplorer -HealthReport $h
    }

    return $h
}

function Show-FAFOVerifoneHealthFlag {
    <#
    .SYNOPSIS
      Drill into a health flag (GridView of sample/full issue set).
    .EXAMPLE
      Show-FAFOVerifoneHealthFlag -Id ZeroPrice
      Show-FAFOVerifoneHealthFlag -Id EmptyDepartment
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateSet(
            'ZeroPrice', 'MissingPrice', 'MissingProductCode', 'MissingUPC',
            'MissingDescription', 'EmptyDepartment', 'OrphanDepartment',
            'InactiveItems', 'DuplicatePLU', 'NoItems', 'NoIdentity'
        )]
        [string]$Id,
        [switch]$PassThru
    )

    $h = Get-FAFOVerifoneHealthReport
    $flag = @($h.Flags | Where-Object Id -eq $Id) | Select-Object -First 1
    if (-not $flag) {
        Write-Host "No open flag: $Id" -ForegroundColor Green
        return @()
    }

    Write-Host ("{0}: {1} (count={2})" -f $flag.Severity, $flag.Title, $flag.Count) -ForegroundColor Yellow
    Write-Host $flag.Hint -ForegroundColor DarkGray

    $rows = switch ($Id) {
        'ZeroPrice' { Get-FAFOVerifoneItem -ZeroPrice }
        'MissingPrice' { Get-FAFOVerifoneItem -MissingPrice }
        'MissingProductCode' { Get-FAFOVerifoneItem -MissingProductCode }
        'MissingUPC' { Get-FAFOVerifoneItem -MissingUPC }
        'MissingDescription' { Get-FAFOVerifoneItem | Where-Object { [string]::IsNullOrWhiteSpace($_.Description) } }
        'EmptyDepartment' { Get-FAFOVerifoneDepartment -WithCounts -EmptyOnly }
        'OrphanDepartment' { Get-FAFOVerifoneItem -OrphanDepartment }
        'InactiveItems' { Get-FAFOVerifoneItem -InactiveOnly }
        'DuplicatePLU' { $flag.Sample }
        default { $flag.Sample }
    }

    $view = @($rows)
    if ($view.Count -eq 0) {
        Write-Host '(no rows)' -ForegroundColor Gray
        return @()
    }

    # Prefer useful columns for items vs depts
    if ($view[0].PSObject.Properties.Name -contains 'PLU') {
        $view = $view | Select-Object PLU, UPC, Description, DepartmentId, Price, ProductCode, Active, Taxable, Discountable, MixMatch
    }
    elseif ($view[0].PSObject.Properties.Name -contains 'ItemCount') {
        $view = $view | Select-Object Id, Name, ItemCount, Category, ProductCode, TaxGroup, IsEmpty
    }

    if (Get-Command Out-GridView -ErrorAction SilentlyContinue) {
        $sel = $view | Out-GridView -Title "Health flag: $Id — $($flag.Title)" -PassThru
        if ($PassThru) { return $sel }
        return $sel
    }
    $view | Format-Table -AutoSize | Out-Host
    if ($PassThru) { return $view }
}

function Show-FAFOVerifoneItem {
    <#
    .SYNOPSIS
      Interactive PLU explorer with filters (Out-GridView when available).
    .EXAMPLE
      Show-FAFOVerifoneItem
      Show-FAFOVerifoneItem -Description '*COKE*' -DepartmentId 1
      Show-FAFOVerifoneItem -MinPrice 5 -MaxPrice 20
    #>
    [CmdletBinding()]
    param(
        [string]$PLU,
        [string]$DepartmentId,
        [string]$Description,
        [string]$ProductCode,
        [nullable[decimal]]$MinPrice,
        [nullable[decimal]]$MaxPrice,
        [switch]$ActiveOnly,
        [switch]$ZeroPrice,
        [switch]$MissingProductCode,
        [switch]$PassThru
    )

    $params = @{}
    foreach ($k in @('PLU', 'DepartmentId', 'Description', 'ProductCode', 'MinPrice', 'MaxPrice')) {
        if ($PSBoundParameters.ContainsKey($k) -and $null -ne $PSBoundParameters[$k] -and $PSBoundParameters[$k] -ne '') {
            $params[$k] = $PSBoundParameters[$k]
        }
    }
    if ($ActiveOnly) { $params['ActiveOnly'] = $true }
    if ($ZeroPrice) { $params['ZeroPrice'] = $true }
    if ($MissingProductCode) { $params['MissingProductCode'] = $true }

    $items = @(Get-FAFOVerifoneItem @params)
    $view = $items | Select-Object PLU, UPC, Description, DepartmentId, Price, ProductCode, Taxable, Discountable, Returnable, MixMatch, Active, SourceFile

    $title = 'FAFO Verifone PLUs'
    if ($DepartmentId) { $title += " | Dept $DepartmentId" }
    if ($Description) { $title += " | $Description" }

    if (Get-Command Out-GridView -ErrorAction SilentlyContinue) {
        $sel = $view | Out-GridView -Title $title -PassThru
        if ($PassThru) { return $sel }
        return $sel
    }

    $view | Format-Table -AutoSize | Out-Host
    if ($PassThru) { return $view }
}

function Show-FAFOVerifoneDepartment {
    <#
    .SYNOPSIS
      Browse departments with item counts; optional jump into PLUs for a selected dept.
    .EXAMPLE
      Show-FAFOVerifoneDepartment
      Show-FAFOVerifoneDepartment -DrillIntoItems
    #>
    [CmdletBinding()]
    param(
        [switch]$EmptyOnly,
        [switch]$DrillIntoItems,
        [switch]$PassThru
    )

    $view = @(Get-FAFOVerifoneDepartment -WithCounts -EmptyOnly:$EmptyOnly |
            Select-Object Id, Name, ItemCount, Category, ProductCode, TaxGroup, MinPrice, MaxPrice, IsEmpty, SourceFile)

    $sel = $null
    if (Get-Command Out-GridView -ErrorAction SilentlyContinue) {
        $sel = $view | Out-GridView -Title 'FAFO Verifone Departments (select to drill into PLUs)' -PassThru
    }
    else {
        $view | Format-Table -AutoSize | Out-Host
        if ($DrillIntoItems) {
            $id = Read-Host 'Department Id to open PLUs for (blank=skip)'
            if ($id) { $sel = @($view | Where-Object { [string]$_.Id -eq $id }) }
        }
    }

    if ($DrillIntoItems -or $sel) {
        foreach ($d in @($sel)) {
            if (-not $d) { continue }
            Write-Host ("Department {0} — {1} ({2} items)" -f $d.Id, $d.Name, $d.ItemCount) -ForegroundColor Cyan
            Show-FAFOVerifoneItem -DepartmentId $d.Id | Out-Null
        }
    }

    if ($PassThru) { return $sel }
    return $sel
}

function Invoke-FAFOVerifoneHealthExplorer {
    <#
    .SYNOPSIS
      Guided surface → drill-down menu for the System Health Report.
    #>
    [CmdletBinding()]
    param(
        [object]$HealthReport
    )

    Assert-FAFOVerifoneSession | Out-Null
    if (-not $HealthReport) {
        $HealthReport = Show-FAFOVerifoneHealthReport
    }

    while ($true) {
        Write-Host ''
        Write-Host 'Health drill-down' -ForegroundColor Cyan
        Write-Host '----------------'
        Write-Host '[1] Re-show surface health report'
        Write-Host '[2] Explore ALL PLUs (filterable GridView)'
        Write-Host '[3] Explore Departments → jump to items'
        Write-Host '[4] Open a health FLAG by number'
        Write-Host '[5] Search PLUs (description / dept / price)'
        Write-Host '[6] Empty departments only'
        Write-Host '[7] Orphan department items'
        Write-Host '[8] Zero-price PLUs'
        Write-Host '[9] Missing product codes'
        Write-Host '[0] Back / exit'
        $c = Read-Host 'Choice'
        switch ($c) {
            '1' { $HealthReport = Show-FAFOVerifoneHealthReport }
            '2' { Show-FAFOVerifoneItem | Out-Null }
            '3' { Show-FAFOVerifoneDepartment -DrillIntoItems | Out-Null }
            '4' {
                if (-not $HealthReport.Flags -or $HealthReport.Flags.Count -eq 0) {
                    Write-Host 'No flags.' -ForegroundColor Green
                    break
                }
                $n = 1
                $HealthReport.Flags | ForEach-Object {
                    Write-Host ("  [{0}] {1}" -f $n, $_.Title)
                    $n++
                }
                $pick = Read-Host 'Flag number'
                $idx = 0
                if ([int]::TryParse($pick, [ref]$idx) -and $idx -ge 1 -and $idx -le $HealthReport.Flags.Count) {
                    Show-FAFOVerifoneHealthFlag -Id $HealthReport.Flags[$idx - 1].Id | Out-Null
                }
            }
            '5' {
                $desc = Read-Host 'Description contains (optional)'
                $dept = Read-Host 'Department Id (optional)'
                $min = Read-Host 'Min price (optional)'
                $max = Read-Host 'Max price (optional)'
                $p = @{}
                if ($desc) { $p.Description = $desc }
                if ($dept) { $p.DepartmentId = $dept }
                if ($min) { try { $p.MinPrice = [decimal]$min } catch { } }
                if ($max) { try { $p.MaxPrice = [decimal]$max } catch { } }
                Show-FAFOVerifoneItem @p | Out-Null
            }
            '6' { Show-FAFOVerifoneDepartment -EmptyOnly | Out-Null }
            '7' { Show-FAFOVerifoneHealthFlag -Id OrphanDepartment | Out-Null }
            '8' { Show-FAFOVerifoneHealthFlag -Id ZeroPrice | Out-Null }
            '9' { Show-FAFOVerifoneHealthFlag -Id MissingProductCode | Out-Null }
            '0' { return }
            default { Write-Host 'Unknown choice' -ForegroundColor Yellow }
        }
    }
}

function Invoke-FAFOVerifoneExplorer {
    <#
    .SYNOPSIS
      Field-tech menu: health, exploration, pricing, library scripts.
    #>
    [CmdletBinding()]
    param()

    Assert-FAFOVerifoneSession | Out-Null

    while ($true) {
        $s = Get-FAFOVerifoneBackup
        Write-Host ''
        Write-Host 'FAFO Verifone Explorer' -ForegroundColor Cyan
        Write-Host '---------------------'
        if ($s.Library) {
            Write-Host ("Site: {0} / {1} / {2}" -f $s.Store.MOC, $s.Store.Customer, $s.Store.Location) -ForegroundColor DarkCyan
        }
        Write-Host '[1] System Health Report (surface)'
        Write-Host '[2] Health drill-down menu'
        Write-Host '[3] Browse PLUs (GridView + filters)'
        Write-Host '[4] Browse Departments → items'
        Write-Host '[5] Show pending price changes'
        Write-Host '[6] Mass price change (% all items)'
        Write-Host '[7] Department price change (%)'
        Write-Host '[8] Individual PLU price edit'
        Write-Host '[9] Export price change log (JSON/CSV)'
        Write-Host '[L] Show library sites'
        Write-Host '[S] Save pending changes as edit SCRIPT (library)'
        Write-Host '[H] Show edit script history'
        Write-Host '[R] Rollback scripts (ToSequence / StepsBack)'
        Write-Host '[W] Save working copy now'
        Write-Host '[0] Exit'
        $c = Read-Host 'Choice'
        switch ($c) {
            '1' { Show-FAFOVerifoneHealthReport | Out-Null }
            '2' { Invoke-FAFOVerifoneHealthExplorer }
            '3' {
                $desc = Read-Host 'Filter description (optional)'
                $dept = Read-Host 'Filter department Id (optional)'
                $p = @{}
                if ($desc) { $p.Description = $desc }
                if ($dept) { $p.DepartmentId = $dept }
                Show-FAFOVerifoneItem @p | Out-Null
            }
            '4' { Show-FAFOVerifoneDepartment -DrillIntoItems | Out-Null }
            '5' { Get-FAFOVerifonePriceChange | Format-Table -AutoSize | Out-Host }
            '6' {
                $pct = Read-Host 'Percent change (e.g. 5 or -2.5)'
                try {
                    $p = [decimal]$pct
                    Set-FAFOVerifoneMassPrice -Percent $p | Format-Table -AutoSize | Out-Host
                }
                catch { Write-Host "Invalid percent: $pct" -ForegroundColor Yellow }
            }
            '7' {
                $d = Read-Host 'Department Id'
                $pct = Read-Host 'Percent change (e.g. 5 or -2.5)'
                try {
                    $p = [decimal]$pct
                    Set-FAFOVerifoneDepartmentPrice -DepartmentId $d -Percent $p | Format-Table -AutoSize | Out-Host
                }
                catch { Write-Host "Invalid percent: $pct" -ForegroundColor Yellow }
            }
            '8' {
                $plu = Read-Host 'PLU'
                $price = Read-Host 'New price'
                try {
                    $p = [decimal]$price
                    Set-FAFOVerifoneItemPrice -PLU $plu -NewPrice $p | Format-List | Out-Host
                }
                catch { Write-Host "Invalid price: $price" -ForegroundColor Yellow }
            }
            '9' {
                $out = Export-FAFOVerifonePriceChange
                Write-Host "Exported: $($out.JsonPath)" -ForegroundColor Green
            }
            { $_ -in @('L', 'l') } { Show-FAFOVerifoneLibrary | Out-Null }
            { $_ -in @('S', 's') } {
                $label = Read-Host 'Script label'
                try { Save-FAFOVerifoneEditScript -Label $label | Format-List | Out-Host }
                catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
            }
            { $_ -in @('H', 'h') } {
                try { Get-FAFOVerifoneEditScript | Format-Table -AutoSize | Out-Host }
                catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
            }
            { $_ -in @('R', 'r') } {
                $mode = Read-Host 'Rollback mode: [S]equence number or [B]steps back'
                try {
                    if ($mode -match '^[Bb]') {
                        $n = [int](Read-Host 'Steps back')
                        Restore-FAFOVerifoneEditScript -StepsBack $n | Format-List | Out-Host
                    }
                    else {
                        $n = [int](Read-Host 'Apply through sequence # (0=original only)')
                        Restore-FAFOVerifoneEditScript -ToSequence $n | Format-List | Out-Host
                    }
                }
                catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
            }
            { $_ -in @('W', 'w') } {
                try { Write-Host "Working: $(Save-FAFOVerifoneWorkingCopy)" -ForegroundColor Green }
                catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
            }
            '0' { return }
            default { Write-Host 'Unknown choice' -ForegroundColor Yellow }
        }
    }
}

#endregion

#region Pricing edits

function Get-FAFOVerifonePriceChange {
    [CmdletBinding()]
    param()
    $s = Assert-FAFOVerifoneSession
    @($s.PriceChanges)
}

function Set-FAFOVerifoneItemPrice {
    <#
    .SYNOPSIS
      Set a single PLU price (in-memory + XML node write-back).
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)]
        [string]$PLU,
        [Parameter(Mandatory)]
        [decimal]$NewPrice,
        [string]$Reason = 'Individual edit'
    )

    $s = Assert-FAFOVerifoneSession
    $item = @($s.Items | Where-Object { [string]$_.PLU -eq $PLU }) | Select-Object -First 1
    if (-not $item) { throw "PLU not found: $PLU" }

    $old = $item.Price
    if ($PSCmdlet.ShouldProcess("PLU $PLU", "Set price $old -> $NewPrice")) {
        $item.Price = $NewPrice
        $item.PriceRaw = "$NewPrice"
        if ($item._XmlNode) { Set-FAFOVerifoneNodePrice -Node $item._XmlNode -NewPrice $NewPrice | Out-Null }
        $change = [PSCustomObject]@{
            Scope      = 'Individual'
            PLU        = $item.PLU
            Description = $item.Description
            DepartmentId = $item.DepartmentId
            OldPrice   = $old
            NewPrice   = $NewPrice
            Reason     = $Reason
            ChangedAt  = Get-Date
        }
        $s.PriceChanges.Add($change) | Out-Null
        $s.IsDirty = $true
        return $change
    }
}

function Set-FAFOVerifoneDepartmentPrice {
    <#
    .SYNOPSIS
      Adjust all item prices in a department by percent or set absolute price.
    .EXAMPLE
      Set-FAFOVerifoneDepartmentPrice -DepartmentId 1 -Percent 5
      Set-FAFOVerifoneDepartmentPrice -DepartmentId 4 -NewPrice 2.99
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)]
        [string]$DepartmentId,
        [decimal]$Percent,
        [decimal]$NewPrice,
        [string]$Reason
    )

    if (-not $PSBoundParameters.ContainsKey('Percent') -and -not $PSBoundParameters.ContainsKey('NewPrice')) {
        throw 'Specify -Percent or -NewPrice'
    }

    $s = Assert-FAFOVerifoneSession
    $targets = @($s.Items | Where-Object { [string]$_.DepartmentId -eq $DepartmentId })
    if ($targets.Count -eq 0) { throw "No items in department '$DepartmentId'" }

    if (-not $Reason) {
        $Reason = if ($PSBoundParameters.ContainsKey('Percent')) {
            "Department $DepartmentId percent $Percent"
        }
        else {
            "Department $DepartmentId absolute $NewPrice"
        }
    }

    $changes = [System.Collections.Generic.List[object]]::new()
    foreach ($item in $targets) {
        if ($null -eq $item.Price -and -not $PSBoundParameters.ContainsKey('NewPrice')) { continue }
        $old = $item.Price
        $next = if ($PSBoundParameters.ContainsKey('NewPrice')) {
            $NewPrice
        }
        else {
            [math]::Round(([decimal]$item.Price) * ([decimal]1 + ($Percent / [decimal]100)), 3)
        }
        if ($PSCmdlet.ShouldProcess("PLU $($item.PLU)", "Dept price $old -> $next")) {
            $item.Price = $next
            $item.PriceRaw = "$next"
            if ($item._XmlNode) { Set-FAFOVerifoneNodePrice -Node $item._XmlNode -NewPrice $next | Out-Null }
            $c = [PSCustomObject]@{
                Scope        = 'Department'
                PLU          = $item.PLU
                Description  = $item.Description
                DepartmentId = $item.DepartmentId
                OldPrice     = $old
                NewPrice     = $next
                Reason       = $Reason
                ChangedAt    = Get-Date
            }
            $s.PriceChanges.Add($c) | Out-Null
            $changes.Add($c) | Out-Null
        }
    }
    if ($changes.Count -gt 0) { $s.IsDirty = $true }
    Write-FAFOVerifoneHost ("Department {0}: {1} price(s) updated" -f $DepartmentId, $changes.Count) 'Green'
    return @($changes)
}

function Set-FAFOVerifoneMassPrice {
    <#
    .SYNOPSIS
      Mass price change across all (or filtered) items by percent.
    .EXAMPLE
      Set-FAFOVerifoneMassPrice -Percent 3
      Set-FAFOVerifoneMassPrice -Percent -1.5 -Description '*COKE*'
    #>
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [Parameter(Mandatory)]
        [decimal]$Percent,
        [string]$DepartmentId,
        [string]$Description,
        [string]$Reason
    )

    $s = Assert-FAFOVerifoneSession
    $targets = @(Get-FAFOVerifoneItem -DepartmentId $DepartmentId -Description $Description)
    $targets = @($targets | Where-Object { $null -ne $_.Price })
    if ($targets.Count -eq 0) { throw 'No matching items with prices to update' }

    if (-not $Reason) { $Reason = "Mass percent $Percent" }

    $changes = [System.Collections.Generic.List[object]]::new()
    foreach ($item in $targets) {
        $old = $item.Price
        $next = [math]::Round(([decimal]$item.Price) * ([decimal]1 + ($Percent / [decimal]100)), 3)
        if ($PSCmdlet.ShouldProcess("PLU $($item.PLU)", "Mass price $old -> $next")) {
            $item.Price = $next
            $item.PriceRaw = "$next"
            if ($item._XmlNode) { Set-FAFOVerifoneNodePrice -Node $item._XmlNode -NewPrice $next | Out-Null }
            $c = [PSCustomObject]@{
                Scope        = 'Mass'
                PLU          = $item.PLU
                Description  = $item.Description
                DepartmentId = $item.DepartmentId
                OldPrice     = $old
                NewPrice     = $next
                Reason       = $Reason
                ChangedAt    = Get-Date
            }
            $s.PriceChanges.Add($c) | Out-Null
            $changes.Add($c) | Out-Null
        }
    }
    if ($changes.Count -gt 0) { $s.IsDirty = $true }
    Write-FAFOVerifoneHost ("Mass update: {0} price(s) changed by {1}%" -f $changes.Count, $Percent) 'Green'
    return @($changes)
}

function Export-FAFOVerifonePriceChange {
    <#
    .SYNOPSIS
      Export pending price changes for audit / restore prep (JSON + CSV).
    #>
    [CmdletBinding()]
    param(
        [string]$Destination
    )

    $s = Assert-FAFOVerifoneSession
    if (-not $Destination) {
        if (Get-Command Get-FAFOToolboxRoot -ErrorAction SilentlyContinue) {
            $root = Get-FAFOToolboxRoot
            $Destination = Join-Path $root 'Reports\Raw'
        }
        else {
            $Destination = Join-Path $env:TEMP 'FAFO-Verifone-Exports'
        }
    }
    if (-not (Test-Path -LiteralPath $Destination)) {
        New-Item -Path $Destination -ItemType Directory -Force | Out-Null
    }

    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $jsonPath = Join-Path $Destination "Verifone-PriceChanges-$stamp.json"
    $csvPath = Join-Path $Destination "Verifone-PriceChanges-$stamp.csv"

    $payload = [PSCustomObject]@{
        ExportedAt = Get-Date
        BackupPath = $s.RootPath
        Store      = $s.Store
        Changes    = @($s.PriceChanges)
    }
    $payload | ConvertTo-Json -Depth 6 | Out-File -FilePath $jsonPath -Encoding utf8
    if ($s.PriceChanges.Count -gt 0) {
        $s.PriceChanges | Export-Csv -Path $csvPath -NoTypeInformation -Encoding utf8
    }
    else {
        '' | Out-File -FilePath $csvPath -Encoding utf8
    }

    [PSCustomObject]@{
        JsonPath     = $jsonPath
        CsvPath      = $csvPath
        ChangeCount  = $s.PriceChanges.Count
    }
}

function Save-FAFOVerifoneBackup {
    <#
    .SYNOPSIS
      Write a copy of the backup with in-memory XML modifications (restore prep).
    .DESCRIPTION
      Copies original tree to Destination, then overwrites XML files that were loaded
      using the in-memory XmlDocument state (including price edits).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Destination
    )

    $s = Assert-FAFOVerifoneSession
    if (-not (Test-Path -LiteralPath $Destination)) {
        New-Item -Path $Destination -ItemType Directory -Force | Out-Null
    }
    $dest = (Resolve-Path -LiteralPath $Destination).Path
    $rootFull = (Resolve-Path -LiteralPath $s.RootPath).Path

    # Only seed destination from source when writing to a different folder
    if ($dest.TrimEnd('\') -ne $rootFull.TrimEnd('\')) {
        Copy-Item -Path (Join-Path $s.RootPath '*') -Destination $dest -Recurse -Force
    }

    $written = 0
    foreach ($path in $s.XmlByPath.Keys) {
        $doc = $s.XmlByPath[$path]
        $rel = $path.Substring($s.RootPath.Length).TrimStart('\', '/')
        $out = Join-Path $dest $rel
        $outDir = Split-Path -Parent $out
        if (-not (Test-Path $outDir)) { New-Item -Path $outDir -ItemType Directory -Force | Out-Null }
        $settings = [System.Xml.XmlWriterSettings]::new()
        $settings.Indent = $true
        $settings.Encoding = [System.Text.UTF8Encoding]::new($false)
        $writer = [System.Xml.XmlWriter]::Create($out, $settings)
        try {
            $doc.Save($writer)
            $written++
        }
        finally {
            $writer.Dispose()
        }
    }

    # Manifest for recovery
    $manifest = [PSCustomObject]@{
        SavedAt        = Get-Date
        SourceBackup   = $s.RootPath
        Destination    = $dest
        Store          = $s.Store
        PriceChangeCount = $s.PriceChanges.Count
        PriceChanges   = @($s.PriceChanges)
        XmlFilesWritten = $written
    }
    $manifestPath = Join-Path $dest "FAFO-Verifone-RestoreManifest.json"
    $manifest | ConvertTo-Json -Depth 6 | Out-File -FilePath $manifestPath -Encoding utf8

    Write-FAFOVerifoneHost ("Saved modified backup -> {0} ({1} xml files)" -f $dest, $written) 'Green'
    [PSCustomObject]@{
        Destination  = $dest
        ManifestPath = $manifestPath
        XmlWritten   = $written
        IsDirty      = $s.IsDirty
    }
}

function Export-FAFOVerifoneSnapshot {
    <#
    .SYNOPSIS
      Export a JSON snapshot of structured data (for HTML/Python tools later).
    #>
    [CmdletBinding()]
    param([string]$Path)

    $s = Assert-FAFOVerifoneSession
    if (-not $Path) {
        if (Get-Command Get-FAFOToolboxRoot -ErrorAction SilentlyContinue) {
            $Path = Join-Path (Get-FAFOToolboxRoot) ("Reports\Raw\Verifone-Snapshot-{0:yyyyMMdd-HHmmss}.json" -f (Get-Date))
        }
        else {
            $Path = Join-Path $env:TEMP ("Verifone-Snapshot-{0:yyyyMMdd-HHmmss}.json" -f (Get-Date))
        }
    }
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -Path $dir -ItemType Directory -Force | Out-Null }

    $snap = [PSCustomObject]@{
        ExportedAt  = Get-Date
        RootPath    = $s.RootPath
        Store       = $s.Store
        Departments = @($s.Departments | Select-Object Id, Name, TaxGroup, SourceFile)
        Items       = @($s.Items | Select-Object PLU, UPC, Description, DepartmentId, Price, ProductCode, Taxable, Discountable, Returnable, MixMatch, Active, SourceFile)
        Taxes       = @($s.Taxes | Select-Object Id, Name, Rate, SourceFile)
        Tenders     = @($s.Tenders | Select-Object Id, Name, Type, SourceFile)
        Fuel        = @($s.Fuel | Select-Object PLU, UPC, Description, DepartmentId, Price, ProductCode, Active, SourceFile)
        DepartmentsDetailed = @($s.Departments | Select-Object Id, Name, TaxGroup, ProductCode, Category, MinPrice, MaxPrice, SourceFile)
        Files       = $s.Files
        PriceChanges = @($s.PriceChanges)
    }
    # Avoid serializing Xml nodes
    $snap | ConvertTo-Json -Depth 6 | Out-File -FilePath $Path -Encoding utf8
    Write-FAFOVerifoneHost "Snapshot: $Path" 'Green'
    return $Path
}

#endregion

#region Site library (MOC / Customer / Location) + scripted rollback

function Get-FAFOVerifoneLibraryRoot {
    <#
    .SYNOPSIS
      Root of the on-disk Verifone backup library (under the toolbox by default).
    #>
    [CmdletBinding()]
    param(
        [string]$ToolboxRoot
    )
    if (-not $ToolboxRoot) {
        if ($env:FAFO_TOOLBOX_ROOT -and (Test-Path $env:FAFO_TOOLBOX_ROOT)) {
            $ToolboxRoot = $env:FAFO_TOOLBOX_ROOT
        }
        elseif (Get-Command Get-FAFOToolboxRoot -ErrorAction SilentlyContinue) {
            $ToolboxRoot = Get-FAFOToolboxRoot
        }
        else {
            # Scripts\Modules\FAFO.Verifone -> toolbox root
            $ToolboxRoot = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
        }
    }
    $root = Join-Path $ToolboxRoot 'VerifoneLibrary'
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -Path $root -ItemType Directory -Force | Out-Null
    }
    return (Resolve-Path -LiteralPath $root).Path
}

function Get-FAFOVerifoneSitePath {
    <#
    .SYNOPSIS
      Build library path: Library\MOC\Customer\Location
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$MOC,
        [Parameter(Mandatory)][string]$Customer,
        [Parameter(Mandatory)][string]$Location,
        [string]$LibraryRoot = (Get-FAFOVerifoneLibraryRoot)
    )
    $p = Join-Path $LibraryRoot (ConvertTo-FAFOSafeName $MOC 'Unknown-MOC')
    $p = Join-Path $p (ConvertTo-FAFOSafeName $Customer 'Unknown-Customer')
    $p = Join-Path $p (ConvertTo-FAFOSafeName $Location 'Unknown-Location')
    return $p
}

function Read-FAFOVerifoneScriptLog {
    param([string]$ScriptsPath)
    $logPath = Join-Path $ScriptsPath 'script-log.json'
    if (-not (Test-Path -LiteralPath $logPath)) {
        return [PSCustomObject]@{
            Scripts         = @()
            AppliedThrough  = 0
            UpdatedAt       = $null
        }
    }
    try {
        return (Get-Content -LiteralPath $logPath -Raw | ConvertFrom-Json)
    }
    catch {
        return [PSCustomObject]@{ Scripts = @(); AppliedThrough = 0; UpdatedAt = $null }
    }
}

function Write-FAFOVerifoneScriptLog {
    param(
        [string]$ScriptsPath,
        [object]$Log
    )
    if (-not (Test-Path -LiteralPath $ScriptsPath)) {
        New-Item -Path $ScriptsPath -ItemType Directory -Force | Out-Null
    }
    $Log.UpdatedAt = (Get-Date).ToString('o')
    $logPath = Join-Path $ScriptsPath 'script-log.json'
    $Log | ConvertTo-Json -Depth 8 | Out-File -FilePath $logPath -Encoding utf8
    return $logPath
}

function Write-FAFOVerifoneSiteMeta {
    param(
        [string]$SitePath,
        [object]$Store,
        [string]$SourcePath,
        [string]$IngestedAt = (Get-Date).ToString('o')
    )
    $meta = [PSCustomObject]@{
        MOC          = $Store.MOC
        Customer     = $Store.Customer
        Location     = $Store.Location
        Name         = $Store.Name
        SiteId       = $Store.SiteId
        Version      = $Store.Version
        Address      = $Store.Address
        BackupDate   = $Store.BackupDate
        SourcePath   = $SourcePath
        IngestedAt   = $IngestedAt
        SitePath     = $SitePath
        OriginalPath = Join-Path $SitePath 'original'
        WorkingPath  = Join-Path $SitePath 'working'
        ScriptsPath  = Join-Path $SitePath 'scripts'
    }
    $metaPath = Join-Path $SitePath 'site.json'
    $meta | ConvertTo-Json -Depth 6 | Out-File -FilePath $metaPath -Encoding utf8
    return $meta
}

function Update-FAFOVerifoneLibraryIndex {
    [CmdletBinding()]
    param([string]$LibraryRoot = (Get-FAFOVerifoneLibraryRoot))

    $sites = @(Get-ChildItem -LiteralPath $LibraryRoot -Filter site.json -File -Recurse -ErrorAction SilentlyContinue)
    $entries = foreach ($f in $sites) {
        try {
            $m = Get-Content -LiteralPath $f.FullName -Raw | ConvertFrom-Json
            [PSCustomObject]@{
                MOC        = $m.MOC
                Customer   = $m.Customer
                Location   = $m.Location
                Name       = $m.Name
                SiteId     = $m.SiteId
                SitePath   = $m.SitePath
                IngestedAt = $m.IngestedAt
                MetaPath   = $f.FullName
            }
        }
        catch { }
    }
    $index = [PSCustomObject]@{
        UpdatedAt = (Get-Date).ToString('o')
        Count     = @($entries).Count
        Sites     = @($entries)
    }
    $indexPath = Join-Path $LibraryRoot '_index.json'
    $index | ConvertTo-Json -Depth 6 | Out-File -FilePath $indexPath -Encoding utf8
    return $index
}

function Get-FAFOVerifoneLibrarySite {
    <#
    .SYNOPSIS
      List or filter sites in the Verifone library (by MOC / Customer / Location / SiteId / Name).
    .EXAMPLE
      Get-FAFOVerifoneLibrarySite
      Get-FAFOVerifoneLibrarySite -Customer '*Demo*'
      Get-FAFOVerifoneLibrarySite -SiteId VF-DEMO-001
    #>
    [CmdletBinding()]
    param(
        [string]$MOC,
        [string]$Customer,
        [string]$Location,
        [string]$SiteId,
        [string]$Name,
        [string]$LibraryRoot = (Get-FAFOVerifoneLibraryRoot)
    )

    $indexPath = Join-Path $LibraryRoot '_index.json'
    if (Test-Path -LiteralPath $indexPath) {
        try {
            $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
            $sites = @($index.Sites)
        }
        catch {
            $sites = @()
        }
    }
    else {
        $sites = @((Update-FAFOVerifoneLibraryIndex -LibraryRoot $LibraryRoot).Sites)
    }

    # Refresh from disk if index empty but folders exist
    if ($sites.Count -eq 0) {
        $sites = @((Update-FAFOVerifoneLibraryIndex -LibraryRoot $LibraryRoot).Sites)
    }

    if ($MOC) { $sites = $sites | Where-Object { $_.MOC -like $MOC } }
    if ($Customer) { $sites = $sites | Where-Object { $_.Customer -like $Customer } }
    if ($Location) { $sites = $sites | Where-Object { $_.Location -like $Location } }
    if ($SiteId) { $sites = $sites | Where-Object { $_.SiteId -like $SiteId } }
    if ($Name) { $sites = $sites | Where-Object { $_.Name -like $Name } }

    $sites | Sort-Object MOC, Customer, Location
}

function Resolve-FAFOVerifoneLibraryContext {
    param([string]$SitePath)

    $sitePath = (Resolve-Path -LiteralPath $SitePath).Path
    $metaPath = Join-Path $sitePath 'site.json'
    $meta = $null
    if (Test-Path -LiteralPath $metaPath) {
        $meta = Get-Content -LiteralPath $metaPath -Raw | ConvertFrom-Json
    }
    $original = Join-Path $sitePath 'original'
    $working = Join-Path $sitePath 'working'
    $scripts = Join-Path $sitePath 'scripts'
    foreach ($d in @($original, $working, $scripts)) {
        if (-not (Test-Path -LiteralPath $d)) {
            New-Item -Path $d -ItemType Directory -Force | Out-Null
        }
    }
    [PSCustomObject]@{
        SitePath     = $sitePath
        OriginalPath = $original
        WorkingPath  = $working
        ScriptsPath  = $scripts
        Meta         = $meta
        MetaPath     = $metaPath
    }
}

function Set-FAFOVerifoneSessionLibrary {
    param([object]$LibraryContext)
    $s = Assert-FAFOVerifoneSession
    $s.Library = $LibraryContext
}

function Save-FAFOVerifoneWorkingCopy {
    <#
    .SYNOPSIS
      Write current in-memory XML state into the site working\ folder (never original\).
    #>
    [CmdletBinding()]
    param()
    $s = Assert-FAFOVerifoneSession
    if (-not $s.Library -or -not $s.Library.WorkingPath) {
        throw 'Session is not bound to a library site. Use Add-FAFOVerifoneLibraryBackup or Open-FAFOVerifoneLibrarySite.'
    }
    Save-FAFOVerifoneBackup -Destination $s.Library.WorkingPath | Out-Null
    return $s.Library.WorkingPath
}

function Add-FAFOVerifoneLibraryBackup {
    <#
    .SYNOPSIS
      Ingest a Verifone backup into the site library BEFORE edits.
      Path: VerifoneLibrary\{MOC}\{Customer}\{Location}\original|working|scripts
    .DESCRIPTION
      Reads site identity from the backup XML when possible. Optional -MOC/-Customer/-Location
      overrides fill gaps or force placement. Original is stored immutable; working starts as a copy.
    .EXAMPLE
      Add-FAFOVerifoneLibraryBackup -Path 'D:\FromUSB\StoreBackup'
      Add-FAFOVerifoneLibraryBackup -Path (Get-FAFOVerifoneDemoBackupPath)
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Path,
        [string]$MOC,
        [string]$Customer,
        [string]$Location,
        [switch]$Force,
        [string]$LibraryRoot = (Get-FAFOVerifoneLibraryRoot)
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Backup path not found: $Path"
    }
    $source = (Resolve-Path -LiteralPath $Path).Path

    # Probe identity without polluting final session path yet
    $probe = Import-FAFOVerifoneBackup -Path $source
    $store = $probe.Store

    $useMoc = if ($MOC) { $MOC } else { $store.MOC }
    $useCustomer = if ($Customer) { $Customer } else { $store.Customer }
    $useLocation = if ($Location) { $Location } else { $store.Location }

    # Reflect overrides onto store for metadata
    $store.MOC = $useMoc
    $store.Customer = $useCustomer
    $store.Location = $useLocation

    $sitePath = Get-FAFOVerifoneSitePath -MOC $useMoc -Customer $useCustomer -Location $useLocation -LibraryRoot $LibraryRoot
    $original = Join-Path $sitePath 'original'
    $working = Join-Path $sitePath 'working'
    $scripts = Join-Path $sitePath 'scripts'

    if ((Test-Path -LiteralPath (Join-Path $original '*')) -and -not $Force) {
        throw "Library site already has an original backup at:`n  $sitePath`nUse -Force to replace original (destroys prior original + scripts), or Open-FAFOVerifoneLibrarySite to work with it."
    }

    if ($Force -and (Test-Path -LiteralPath $sitePath)) {
        Remove-Item -LiteralPath $sitePath -Recurse -Force
    }

    New-Item -Path $original -ItemType Directory -Force | Out-Null
    New-Item -Path $working -ItemType Directory -Force | Out-Null
    New-Item -Path $scripts -ItemType Directory -Force | Out-Null

    # Immutable original
    Copy-Item -Path (Join-Path $source '*') -Destination $original -Recurse -Force
    # Working starts identical
    Copy-Item -Path (Join-Path $original '*') -Destination $working -Recurse -Force

    # Fresh script log
    Write-FAFOVerifoneScriptLog -ScriptsPath $scripts -Log ([PSCustomObject]@{
            Scripts        = @()
            AppliedThrough = 0
            UpdatedAt      = $null
        }) | Out-Null

    $meta = Write-FAFOVerifoneSiteMeta -SitePath $sitePath -Store $store -SourcePath $source
    Update-FAFOVerifoneLibraryIndex -LibraryRoot $LibraryRoot | Out-Null

    # Load working for editing
    $session = Import-FAFOVerifoneBackup -Path $working
    $ctx = Resolve-FAFOVerifoneLibraryContext -SitePath $sitePath
    $ctx = [PSCustomObject]@{
        SitePath     = $ctx.SitePath
        OriginalPath = $ctx.OriginalPath
        WorkingPath  = $ctx.WorkingPath
        ScriptsPath  = $ctx.ScriptsPath
        Meta         = $meta
        MetaPath     = $ctx.MetaPath
    }
    Set-FAFOVerifoneSessionLibrary -LibraryContext $ctx

    Write-FAFOVerifoneHost 'Ingested into library (original sealed, working ready):' 'Green'
    Write-FAFOVerifoneHost "  $sitePath" 'Green'
    Write-FAFOVerifoneHost ("  MOC={0} | Customer={1} | Location={2}" -f $useMoc, $useCustomer, $useLocation) 'Gray'

    [PSCustomObject]@{
        SitePath     = $sitePath
        OriginalPath = $original
        WorkingPath  = $working
        ScriptsPath  = $scripts
        Meta         = $meta
        Session      = $session
    }
}

function Open-FAFOVerifoneLibrarySite {
    <#
    .SYNOPSIS
      Open a library site for editing (loads working\ + binds library context).
    .EXAMPLE
      Open-FAFOVerifoneLibrarySite -SiteId VF-DEMO-001
      Open-FAFOVerifoneLibrarySite -MOC 'FAFO*' -Customer '*Demo*' -Location '*Main*'
    #>
    [CmdletBinding(DefaultParameterSetName = 'Filter')]
    param(
        [Parameter(ParameterSetName = 'Filter')][string]$MOC,
        [Parameter(ParameterSetName = 'Filter')][string]$Customer,
        [Parameter(ParameterSetName = 'Filter')][string]$Location,
        [Parameter(ParameterSetName = 'Filter')][string]$SiteId,
        [Parameter(ParameterSetName = 'Filter')][string]$Name,
        [Parameter(ParameterSetName = 'Path', Mandatory)][string]$SitePath,
        [switch]$FromOriginal
    )

    if ($PSCmdlet.ParameterSetName -eq 'Path') {
        $path = $SitePath
    }
    else {
        $hits = @(Get-FAFOVerifoneLibrarySite -MOC $MOC -Customer $Customer -Location $Location -SiteId $SiteId -Name $Name)
        if ($hits.Count -eq 0) { throw 'No library sites matched.' }
        if ($hits.Count -gt 1) {
            Write-Host 'Multiple matches:' -ForegroundColor Yellow
            $hits | Format-Table MOC, Customer, Location, SiteId, Name -AutoSize | Out-Host
            throw 'Narrow your filter (or pass -SitePath).'
        }
        $path = $hits[0].SitePath
    }

    $ctx = Resolve-FAFOVerifoneLibraryContext -SitePath $path
    $loadPath = if ($FromOriginal) { $ctx.OriginalPath } else { $ctx.WorkingPath }
    if (-not (Get-ChildItem -LiteralPath $loadPath -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)) {
        throw "No files under $loadPath"
    }

    $session = Import-FAFOVerifoneBackup -Path $loadPath
    if (Test-Path -LiteralPath $ctx.MetaPath) {
        $ctx = [PSCustomObject]@{
            SitePath     = $ctx.SitePath
            OriginalPath = $ctx.OriginalPath
            WorkingPath  = $ctx.WorkingPath
            ScriptsPath  = $ctx.ScriptsPath
            Meta         = (Get-Content -LiteralPath $ctx.MetaPath -Raw | ConvertFrom-Json)
            MetaPath     = $ctx.MetaPath
        }
    }
    Set-FAFOVerifoneSessionLibrary -LibraryContext $ctx

    $log = Read-FAFOVerifoneScriptLog -ScriptsPath $ctx.ScriptsPath
    Write-FAFOVerifoneHost ("Opened library site: {0}" -f $ctx.SitePath) 'Green'
    Write-FAFOVerifoneHost ("  Applied edit scripts: 1..{0} (of {1})" -f $log.AppliedThrough, @($log.Scripts).Count) 'Gray'
    return $session
}

function Get-FAFOVerifoneEditScript {
    <#
    .SYNOPSIS
      List saved edit scripts for the current library site (or -SitePath).
    #>
    [CmdletBinding()]
    param([string]$SitePath)

    if ($SitePath) {
        $ctx = Resolve-FAFOVerifoneLibraryContext -SitePath $SitePath
    }
    else {
        $s = Assert-FAFOVerifoneSession
        if (-not $s.Library) { throw 'No library site bound. Open a site first.' }
        $ctx = $s.Library
    }

    $log = Read-FAFOVerifoneScriptLog -ScriptsPath $ctx.ScriptsPath
    $scripts = @($log.Scripts)
    foreach ($sc in $scripts) {
        [PSCustomObject]@{
            Seq            = [int]$sc.Seq
            Label          = $sc.Label
            File           = $sc.File
            CreatedAt      = $sc.CreatedAt
            OpCount        = $sc.OpCount
            Applied        = ([int]$sc.Seq -le [int]$log.AppliedThrough)
            AppliedThrough = [int]$log.AppliedThrough
            SitePath       = $ctx.SitePath
        }
    }
}

function Save-FAFOVerifoneEditScript {
    <#
    .SYNOPSIS
      Freeze pending in-session price changes into an append-only edit script.
    .DESCRIPTION
      Does NOT store a full backup copy. Stores only operations (PLU -> NewPrice).
      Updates working\ XML and advances AppliedThrough. Original\ stays untouched.
    .EXAMPLE
      Set-FAFOVerifoneItemPrice -PLU 12345 -NewPrice 2.29
      Save-FAFOVerifoneEditScript -Label 'Coke promo'
    #>
    [CmdletBinding()]
    param(
        [string]$Label = ('edit-{0:yyyyMMdd-HHmmss}' -f (Get-Date))
    )

    $s = Assert-FAFOVerifoneSession
    if (-not $s.Library) {
        throw 'Save-FAFOVerifoneEditScript requires a library site. Ingest with Add-FAFOVerifoneLibraryBackup first.'
    }
    if ($s.PriceChanges.Count -eq 0) {
        throw 'No pending price changes to save as a script.'
    }

    $ctx = $s.Library
    $log = Read-FAFOVerifoneScriptLog -ScriptsPath $ctx.ScriptsPath
    $scripts = @($log.Scripts)
    $nextSeq = 1
    if ($scripts.Count -gt 0) {
        $nextSeq = ([int]($scripts | Measure-Object -Property Seq -Maximum).Maximum) + 1
    }

    # Collapse to precise per-PLU ops (exact rollback replay)
    $ops = foreach ($c in $s.PriceChanges) {
        [PSCustomObject]@{
            Op           = 'SetItemPrice'
            PLU          = [string]$c.PLU
            NewPrice     = $c.NewPrice
            OldPrice     = $c.OldPrice
            Description  = $c.Description
            DepartmentId = $c.DepartmentId
            Scope        = $c.Scope
            Reason       = $c.Reason
        }
    }

    $fileName = ('{0:D4}-{1}.json' -f $nextSeq, (ConvertTo-FAFOSafeName $Label 'edit'))
    $scriptPath = Join-Path $ctx.ScriptsPath $fileName
    $scriptObj = [PSCustomObject]@{
        Seq       = $nextSeq
        Label     = $Label
        CreatedAt = (Get-Date).ToString('o')
        OpCount   = @($ops).Count
        Operations = @($ops)
    }
    $scriptObj | ConvertTo-Json -Depth 8 | Out-File -FilePath $scriptPath -Encoding utf8

    $entry = [PSCustomObject]@{
        Seq       = $nextSeq
        Label     = $Label
        File      = $fileName
        CreatedAt = $scriptObj.CreatedAt
        OpCount   = $scriptObj.OpCount
    }
    $newScripts = @($scripts) + @($entry)
    $newLog = [PSCustomObject]@{
        Scripts        = $newScripts
        AppliedThrough = $nextSeq
        UpdatedAt      = $null
    }
    Write-FAFOVerifoneScriptLog -ScriptsPath $ctx.ScriptsPath -Log $newLog | Out-Null

    # Persist working tree (not original)
    Save-FAFOVerifoneWorkingCopy | Out-Null

    # Clear pending — they are now scripted history
    $s.PriceChanges.Clear()
    $s.IsDirty = $false

    Write-FAFOVerifoneHost ("Saved edit script #{0}: {1} ({2} ops)" -f $nextSeq, $Label, $entry.OpCount) 'Green'
    return $entry
}

function Invoke-FAFOVerifoneScriptOperations {
    param(
        [object[]]$Operations,
        [switch]$Quiet
    )
    $s = Assert-FAFOVerifoneSession
    $applied = 0
    foreach ($op in $Operations) {
        $opName = [string]$op.Op
        switch ($opName) {
            'SetItemPrice' {
                $plu = [string]$op.PLU
                $item = @($s.Items | Where-Object { [string]$_.PLU -eq $plu }) | Select-Object -First 1
                if (-not $item) {
                    if (-not $Quiet) { Write-Warning "Replay skip missing PLU $plu" }
                    continue
                }
                $newPrice = [decimal]$op.NewPrice
                $item.Price = $newPrice
                $item.PriceRaw = "$newPrice"
                if ($item._XmlNode) { Set-FAFOVerifoneNodePrice -Node $item._XmlNode -NewPrice $newPrice | Out-Null }
                $applied++
            }
            default {
                if (-not $Quiet) { Write-Warning "Unknown op: $opName" }
            }
        }
    }
    return $applied
}

function Restore-FAFOVerifoneEditScript {
    <#
    .SYNOPSIS
      Roll working state back by replaying original + scripts 1..N (no full version trees).
    .EXAMPLE
      Restore-FAFOVerifoneEditScript -ToSequence 0          # pure original
      Restore-FAFOVerifoneEditScript -ToSequence 2          # original + scripts 1..2
      Restore-FAFOVerifoneEditScript -StepsBack 1           # undo last applied script
    #>
    [CmdletBinding(DefaultParameterSetName = 'ToSequence')]
    param(
        [Parameter(ParameterSetName = 'ToSequence')]
        [int]$ToSequence,

        [Parameter(ParameterSetName = 'StepsBack')]
        [int]$StepsBack = 1
    )

    $s = Assert-FAFOVerifoneSession
    if (-not $s.Library) { throw 'Not bound to a library site.' }
    $ctx = $s.Library
    $log = Read-FAFOVerifoneScriptLog -ScriptsPath $ctx.ScriptsPath
    $all = @($log.Scripts | Sort-Object { [int]$_.Seq })

    if ($PSCmdlet.ParameterSetName -eq 'StepsBack') {
        $target = [Math]::Max(0, ([int]$log.AppliedThrough) - $StepsBack)
    }
    else {
        $target = $ToSequence
    }
    if ($target -lt 0) { $target = 0 }
    $maxSeq = if ($all.Count) { [int]($all | Measure-Object -Property Seq -Maximum).Maximum } else { 0 }
    if ($target -gt $maxSeq) { $target = $maxSeq }

    # Reset working from immutable original
    if (Test-Path -LiteralPath $ctx.WorkingPath) {
        Get-ChildItem -LiteralPath $ctx.WorkingPath -Force | Remove-Item -Recurse -Force
    }
    else {
        New-Item -Path $ctx.WorkingPath -ItemType Directory -Force | Out-Null
    }
    Copy-Item -Path (Join-Path $ctx.OriginalPath '*') -Destination $ctx.WorkingPath -Recurse -Force

    # Load original baseline into session
    $null = Import-FAFOVerifoneBackup -Path $ctx.WorkingPath
    Set-FAFOVerifoneSessionLibrary -LibraryContext $ctx

    $opsApplied = 0
    $toReplay = @($all | Where-Object { [int]$_.Seq -le $target } | Sort-Object { [int]$_.Seq })
    foreach ($sc in $toReplay) {
        $scriptFile = Join-Path $ctx.ScriptsPath $sc.File
        if (-not (Test-Path -LiteralPath $scriptFile)) {
            Write-Warning "Missing script file: $($sc.File)"
            continue
        }
        $body = Get-Content -LiteralPath $scriptFile -Raw | ConvertFrom-Json
        $opsApplied += Invoke-FAFOVerifoneScriptOperations -Operations @($body.Operations) -Quiet
    }

    # Persist working + update applied pointer (script files remain for future redo)
    Save-FAFOVerifoneWorkingCopy | Out-Null
    $newLog = [PSCustomObject]@{
        Scripts        = $all
        AppliedThrough = $target
        UpdatedAt      = $null
    }
    Write-FAFOVerifoneScriptLog -ScriptsPath $ctx.ScriptsPath -Log $newLog | Out-Null

    $s2 = Assert-FAFOVerifoneSession
    $s2.PriceChanges.Clear()
    $s2.IsDirty = $false

    Write-FAFOVerifoneHost ("Restored to sequence {0} (replayed {1} script(s), {2} ops)" -f $target, $toReplay.Count, $opsApplied) 'Green'
    [PSCustomObject]@{
        AppliedThrough = $target
        ScriptsReplayed = $toReplay.Count
        OpsApplied     = $opsApplied
        WorkingPath    = $ctx.WorkingPath
        OriginalPath   = $ctx.OriginalPath
    }
}

function Redo-FAFOVerifoneEditScript {
    <#
    .SYNOPSIS
      Re-apply scripts beyond current AppliedThrough (e.g. after a partial rollback).
    .EXAMPLE
      Restore-FAFOVerifoneEditScript -ToSequence 1
      Redo-FAFOVerifoneEditScript -ToSequence 3
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [int]$ToSequence
    )
    Restore-FAFOVerifoneEditScript -ToSequence $ToSequence
}

function Show-FAFOVerifoneLibrary {
    <#
    .SYNOPSIS
      Friendly table of library sites for field lookup.
    #>
    [CmdletBinding()]
    param(
        [string]$MOC,
        [string]$Customer,
        [string]$Location,
        [string]$SiteId
    )
    $sites = @(Get-FAFOVerifoneLibrarySite -MOC $MOC -Customer $Customer -Location $Location -SiteId $SiteId)
    if ($sites.Count -eq 0) {
        Write-Host "No sites in library yet. Use Add-FAFOVerifoneLibraryBackup -Path <folder>" -ForegroundColor Yellow
        Write-Host "Library root: $(Get-FAFOVerifoneLibraryRoot)" -ForegroundColor Gray
        return
    }
    Write-Host "Verifone library: $(Get-FAFOVerifoneLibraryRoot)" -ForegroundColor Cyan
    $sites | Format-Table MOC, Customer, Location, SiteId, Name, IngestedAt -AutoSize
    return $sites
}

#endregion

Export-ModuleMember -Function @(
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
    # Library + scripted rollback
    'Get-FAFOVerifoneLibraryRoot',
    'Get-FAFOVerifoneSitePath',
    'Get-FAFOVerifoneLibrarySite',
    'Show-FAFOVerifoneLibrary',
    'Add-FAFOVerifoneLibraryBackup',
    'Open-FAFOVerifoneLibrarySite',
    'Save-FAFOVerifoneWorkingCopy',
    'Get-FAFOVerifoneEditScript',
    'Save-FAFOVerifoneEditScript',
    'Restore-FAFOVerifoneEditScript',
    'Redo-FAFOVerifoneEditScript'
)

