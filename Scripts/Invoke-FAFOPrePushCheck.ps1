# Invoke-FAFOPrePushCheck.ps1
# Lightweight hygiene gate before git commit / push.
# Exit 0 = pass, 1 = fail.

[CmdletBinding()]
param(
    [string]$ToolboxRoot = $env:FAFO_TOOLBOX_ROOT
)

$ErrorActionPreference = 'Stop'

if (-not $ToolboxRoot) {
    $ToolboxRoot = Split-Path -Parent $PSScriptRoot
}
if (-not (Test-Path -LiteralPath $ToolboxRoot)) {
    throw "Toolbox root not found: $ToolboxRoot"
}

$fail = [System.Collections.Generic.List[string]]::new()
$warn = [System.Collections.Generic.List[string]]::new()

function Add-Fail([string]$Message) { $fail.Add($Message) | Out-Null }
function Add-Warn([string]$Message) { $warn.Add($Message) | Out-Null }

Write-Host "=== FAFO Pre-Push Check ===" -ForegroundColor Cyan
Write-Host "Root: $ToolboxRoot"

# --- 1) .gitignore presence & required patterns ---
$gitignorePath = Join-Path $ToolboxRoot '.gitignore'
$requiredPatterns = @(
    'server/security_config.json',
    'Reports/',
    'Logs/',
    'Backups/',
    'Secrets/',
    '.env',
    'Investor Portal.html',
    'server/investor_ops.py',
    'server/xero_ops.py'
)

if (-not (Test-Path -LiteralPath $gitignorePath)) {
    Add-Fail '.gitignore is missing at toolbox root'
}
else {
    $gi = Get-Content -LiteralPath $gitignorePath -Raw -ErrorAction SilentlyContinue
    if ([string]::IsNullOrWhiteSpace($gi)) {
        Add-Fail '.gitignore exists but is empty'
    }
    else {
        foreach ($pat in $requiredPatterns) {
            # Flexible match: allow Backups/ or backups/, trailing slash optional
            $escaped = [regex]::Escape($pat) -replace '\\/', '[\\/]'
            $escaped = $escaped -replace '\\\*\\\*', '.*'
            if ($gi -notmatch $escaped -and $gi -notmatch [regex]::Escape($pat.TrimEnd('/'))) {
                # Case-insensitive contains fallback for Windows
                if ($gi -notlike "*$($pat.TrimEnd('/'))*") {
                    Add-Fail ".gitignore missing required pattern: $pat"
                }
            }
        }
    }
}

# --- 2) Sensitive paths that must not be tracked / staged ---
$blockedRelative = @(
    'Reports',
    'Logs',
    'Backups',
    'backups',
    'terminals',
    'server\security_config.json',
    'Investor Portal.html',
    'Business Tax Preparedness',
    'server\investor_ops.py',
    'server\xero_ops.py',
    'server\_private_investor_routes.py',
    'server\_private_xero_routes.py',
    'System Tools\PC Reports and Log Viewer\catalog.js',
    'System Tools\PC Reports and Log Viewer\logs-data.js',
    'System Tools\PC Reports and Log Viewer\device-local',
    'System Tools\PC Reports and Log Viewer\reports'
)

$gitDir = Join-Path $ToolboxRoot '.git'
$hasGit = Test-Path -LiteralPath $gitDir

function Test-PathLooksSecret([string]$RelativePath, [string]$FullPath) {
    $name = Split-Path -Leaf $RelativePath
    $rel = $RelativePath -replace '/', '\'

    # Allow the FAFO.Secrets *module* (code); block only secret *stores*
    if ($rel -match '(?i)Modules\\FAFO\.Secrets') {
        return $false
    }

    if ($rel -match '(^|\\)Secrets(\\|$)' -or $rel -match '(?i)FAFO\\Secrets(\\|$)' -or
        $rel -match '(?i)FAFO\\Devices(\\|$)' -or
        $rel -match '(^|\\)Reports(\\|$)' -or $rel -match '(^|\\)Logs(\\|$)' -or
        $rel -match '(^|\\)Backups(\\|$)' -or $rel -match '(^|\\)backups(\\|$)' -or
        $rel -match '(^|\\)terminals(\\|$)' -or
        $rel -match '(?i)PC Reports and Log Viewer\\(catalog\.js|logs-data\.js|device-local|reports)(\\|$)') {
        return $true
    }
    if ($name -ieq 'security_config.json') { return $true }
    if ($name -ieq 'Investor Portal.html') { return $true }
    if ($rel -match '(?i)Business Tax Preparedness') { return $true }
    if ($name -match '(?i)(investor_ops|xero_ops|_private_investor|_private_xero)') { return $true }
    if ($name -match '(?i)(^\.env$|\.pem$|\.pfx$|credentials\.json|token\.json)') { return $true }
    if ($name -match '(?i)(api_key|auth_key)') { return $true }
    if ($name -match '(?i)\.xml$' -and $rel -match '(?i)Secrets') { return $true }
    if ($name -match '(?i)\.(db|log)$') { return $true }
    return $false
}

function Test-FileContentSecretish([string]$FullPath) {
    # Only scan small text-ish files
    try {
        $item = Get-Item -LiteralPath $FullPath -ErrorAction Stop
        if ($item.Length -gt 512KB) { return $false }
        $ext = $item.Extension.ToLowerInvariant()
        if ($ext -notin @('.json', '.env', '.txt', '.md', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.ps1', '.py', '.js', '.html', '')) {
            return $false
        }
        $text = Get-Content -LiteralPath $FullPath -Raw -ErrorAction Stop
        if ($text -match '(?im)^\s*abuse_ch_auth_key\s*[:=]\s*["'']?[A-Za-z0-9]{16,}') { return $true }
        if ($text -match '(?im)(api[_-]?key|auth[_-]?key|secret[_-]?key)\s*[:=]\s*["''][^"'']{12,}["'']') { return $true }
        if ($text -match '-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----') { return $true }
        if ($text -match '(?i)xai-[A-Za-z0-9]{20,}') { return $true }
        # Live maint/SSH/API passwords must not ship in the public tree
        if ($text -match '(?i)password\s*[:=]\s*[''"][^''"]{8,}[''"]') { return $true }
    }
    catch {
        return $false
    }
    return $false
}

# On-disk blocked trees present under root (informational if gitignored)
foreach ($rel in $blockedRelative) {
    $p = Join-Path $ToolboxRoot $rel
    if (Test-Path -LiteralPath $p) {
        # ok if ignored; checked via git below when available
    }
}

# security_config.json must not contain a real key
$secCfg = Join-Path $ToolboxRoot 'server\security_config.json'
if (Test-Path -LiteralPath $secCfg) {
    try {
        $cfgText = Get-Content -LiteralPath $secCfg -Raw
        if ($cfgText -match '(?i)"abuse_ch_auth_key"\s*:\s*"[^"]{8,}"') {
            Add-Fail 'server/security_config.json still contains a plaintext abuse_ch_auth_key value'
        }
    }
    catch {
        Add-Warn "Could not read server/security_config.json: $($_.Exception.Message)"
    }
}

# --- 3) Git staged / tracked checks (if repo exists) ---
if ($hasGit) {
    Push-Location $ToolboxRoot
    try {
        $stagedAll = @(git diff --cached --name-only 2>$null | Where-Object { $_ })
        # Files that will remain/appear after commit (exclude pure deletions — untracking sensitive packs is good)
        $stagedKeep = @(git diff --cached --name-only --diff-filter=ACMR 2>$null | Where-Object { $_ })
        $stagedDeleted = @(git diff --cached --name-only --diff-filter=D 2>$null | Where-Object { $_ })
        $tracked = @(git ls-files 2>$null | Where-Object { $_ })
        # Paths still present after this commit (tracked minus staged deletions, plus staged adds/mods)
        $trackedAfter = @($tracked | Where-Object { $stagedDeleted -notcontains $_ }) + @($stagedKeep) | Select-Object -Unique
        $unstaged = @(git diff --name-only 2>$null | Where-Object { $_ })
        $untracked = @(git ls-files --others --exclude-standard 2>$null | Where-Object { $_ })

        $toScan = @($stagedKeep + $trackedAfter + $unstaged + $untracked | Select-Object -Unique)
        Write-Host "Scanning paths (stagedKeep=$($stagedKeep.Count) stagedDel=$($stagedDeleted.Count) trackedAfter=$($trackedAfter.Count) untracked=$($untracked.Count))" -ForegroundColor Gray

        foreach ($rel in $toScan) {
            if ([string]::IsNullOrWhiteSpace($rel)) { continue }
            $full = Join-Path $ToolboxRoot ($rel -replace '/', '\')
            $inNextCommit = ($trackedAfter -contains $rel)
            $inWorking = ($untracked -contains $rel) -or ($unstaged -contains $rel)

            if (Test-PathLooksSecret $rel $full) {
                if ($inNextCommit) {
                    Add-Fail "Sensitive path would remain tracked after commit: $rel"
                }
                elseif ($untracked -contains $rel) {
                    Add-Fail "Sensitive untracked file is not ignored: $rel"
                }
            }

            if ($inNextCommit -and (Test-Path -LiteralPath $full -PathType Leaf)) {
                if (Test-FileContentSecretish $full) {
                    Add-Fail "Secret-like content in tracked/staged file: $rel"
                }
            }
            elseif ($inWorking -and -not $inNextCommit -and (Test-Path -LiteralPath $full -PathType Leaf)) {
                if (Test-FileContentSecretish $full) {
                    Add-Fail "Secret-like content in untracked (not ignored) file: $rel"
                }
            }
        }

        # Explicit: Reports/Logs/Backups must never remain tracked after this commit
        foreach ($prefix in @('Reports/', 'Logs/', 'Backups/', 'backups/', 'terminals/')) {
            $hit = @($trackedAfter | Where-Object {
                    $_ -like ($prefix + '*') -or
                    $_ -like ($prefix.Replace('/', '\') + '*') -or
                    $_ -eq $prefix.TrimEnd('/') -or
                    $_ -eq $prefix.TrimEnd('\').TrimEnd('/')
                })
            if ($hit.Count -gt 0) {
                Add-Fail "Blocked tree has git entries under ${prefix}: $($hit.Count) file(s) e.g. $($hit[0])"
            }
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Add-Warn 'No .git directory yet — skipped staged/tracked scan. Run again after git init.'
    # Without git, still fail if security_config has plaintext (already checked)
    # and if .gitignore missing patterns (already checked)
}

# --- Results ---
Write-Host ''
if ($warn.Count -gt 0) {
    Write-Host "Warnings ($($warn.Count)):" -ForegroundColor Yellow
    $warn | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}

if ($fail.Count -gt 0) {
    Write-Host "FAILED ($($fail.Count)):" -ForegroundColor Red
    $fail | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ''
    Write-Host 'Fix the issues above before committing or pushing.' -ForegroundColor Red
    exit 1
}

Write-Host 'PASSED — safe to commit (still review git status yourself).' -ForegroundColor Green
exit 0
