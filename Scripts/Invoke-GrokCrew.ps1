# Invoke-GrokCrew.ps1 — rank or queue a task for the Grok Bot crew.

[CmdletBinding()]
param(
    [ValidateSet('rank', 'queue', 'roster', 'jobs', 'status')]
    [string]$Action = 'rank',
    [string]$Text,
    [string]$BaseUrl
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'GrokCrew-Lib.ps1')

function Read-BridgeUrl {
    foreach ($p in @(
            (Join-Path $env:LOCALAPPDATA 'FAFO\GrokPsBridge\bridge.json'),
            (Join-Path $env:USERPROFILE '.grok\ps-bridge\bridge.json')
        )) {
        if (Test-Path -LiteralPath $p) {
            try {
                $j = Get-Content -LiteralPath $p -Raw | ConvertFrom-Json
                if ($j.bind) { return $j.bind }
            } catch { }
        }
    }
    return 'http://127.0.0.87:17321'
}

function Invoke-BridgeApi {
    param([string]$Method, [string]$Url, $Body)
    $params = @{ Uri = $Url; Method = $Method; TimeoutSec = 20 }
    if ($null -ne $Body) {
        $params.ContentType = 'application/json'
        $params.Body = ($Body | ConvertTo-Json -Depth 10 -Compress)
    }
    try { return Invoke-RestMethod @params }
    catch { throw "Bridge unreachable at $Url. Start Scripts\Start-GrokPsBridge.ps1 first. $_" }
}

if (-not $BaseUrl) { $BaseUrl = Read-BridgeUrl }
$BaseUrl = $BaseUrl.TrimEnd('/')

switch ($Action) {
    'status' { Invoke-BridgeApi GET "$BaseUrl/health" | ConvertTo-Json -Depth 6 }
    'roster' {
        try { Invoke-BridgeApi GET "$BaseUrl/bots/roster" | ConvertTo-Json -Depth 8 }
        catch { Get-GrokCrewRoster | ConvertTo-Json -Depth 8 }
    }
    'rank' {
        if (-not $Text) { throw 'rank requires -Text' }
        try { Invoke-BridgeApi POST "$BaseUrl/bots/route" @{ text = $Text } | ConvertTo-Json -Depth 10 }
        catch { Get-GrokCrewRank -Text $Text | ConvertTo-Json -Depth 10 }
    }
    'queue' {
        if (-not $Text) { throw 'queue requires -Text' }
        $rank = Get-GrokCrewRank -Text $Text
        $job = @{
            v      = 1
            kind   = 'bot-job'
            from   = 'crew-router'
            text   = $Text
            pick   = $rank.pick
            ask    = $rank.ask_user
            reason = $rank.reason
        }
        try { Invoke-BridgeApi POST "$BaseUrl/bots/jobs" $job | ConvertTo-Json -Depth 10 }
        catch {
            $root = Get-GrokCrewRoots
            $out = Join-Path $root 'outbox'
            New-Item -ItemType Directory -Force -Path $out | Out-Null
            $id = [guid]::NewGuid().ToString('N')
            $job.id = $id
            $job.ts = (Get-Date).ToUniversalTime().ToString('o')
            $path = Join-Path $out ("{0}-{1}.json" -f ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmss')), $id)
            ($job | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $path -Encoding UTF8
            $job | ConvertTo-Json -Depth 10
        }
    }
    'jobs' { Invoke-BridgeApi GET "$BaseUrl/bots/jobs" | ConvertTo-Json -Depth 10 }
}
