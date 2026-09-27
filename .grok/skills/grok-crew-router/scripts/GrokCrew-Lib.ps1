# Shared crew ranking. Dot-source from Invoke-GrokCrew and the bridge.

function Get-GrokCrewRoots {
    $local = Join-Path $env:LOCALAPPDATA 'FAFO\GrokPsBridge'
    New-Item -ItemType Directory -Force -Path $local | Out-Null
    return $local
}

function Get-GrokCrewRosterPath {
    $root = Get-GrokCrewRoots
    $local = Join-Path $root 'roster.json'
    if (Test-Path -LiteralPath $local) { return $local }
    $candidates = @(
        (Join-Path $PSScriptRoot '..\.grok\skills\grok-crew-router\assets\roster.json'),
        (Join-Path $PSScriptRoot '..\..\assets\roster.json')
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    return $local
}

function Get-GrokCrewRoster {
    $path = Get-GrokCrewRosterPath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Roster missing: $path"
    }
    return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Get-GrokCrewRank {
    param([string]$Text, $Roster)
    if (-not $Roster) { $Roster = Get-GrokCrewRoster }
    $hay = ($Text | Out-String).ToLowerInvariant()
    $standing = $hay -match 'from now on|every day|daily|standing|recurring|routine'
    $together = $hay -match 'together|all bots|the crew|coordinate|orchestrat'
    $rows = foreach ($bot in @($Roster.bots)) {
        $blob = (@($bot.name, $bot.title, $bot.role, $bot.notes) + @($bot.keywords)) -join ' '
        $blob = $blob.ToLowerInvariant()
        $score = 0
        foreach ($word in ($hay -split '[^a-z0-9]+' | Where-Object { $_.Length -ge 3 })) {
            if ($blob.Contains($word)) { $score += 1 }
        }
        foreach ($kw in @($bot.keywords)) {
            if ($hay.Contains([string]$kw.ToLowerInvariant())) { $score += 3 }
        }
        if ($together -and $bot.role -eq 'orchestrator') { $score += 8 }
        if ($standing -and $bot.role -eq 'orchestrator') { $score += 4 }
        [pscustomobject]@{
            id     = $bot.id
            name   = $bot.name
            title  = $bot.title
            role   = $bot.role
            score  = $score
            notes  = $bot.notes
        }
    }
    $sorted = @($rows | Sort-Object score -Descending)
    $best = $sorted[0]
    $second = if ($sorted.Count -gt 1) { $sorted[1] } else { $null }
    $gap = if ($second) { $best.score - $second.score } else { $best.score }
    $ask = [bool]($standing -or ($together -and $gap -lt 4) -or ($gap -lt 2 -and $best.score -gt 0))
    [pscustomobject]@{
        task        = $Text
        standing    = [bool]$standing
        together    = [bool]$together
        ask_user    = $ask
        pick        = $best
        alternates  = @($sorted | Select-Object -Skip 1 -First 3)
        ranked      = $sorted
        reason      = if ($ask) { 'Several bots could own this, or it is standing work. Confirm before assign. Default owner: Commander.' } else { "Best match: $($best.name) ($($best.role)) score $($best.score)." }
    }
}
