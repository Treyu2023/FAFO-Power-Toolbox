# Invoke-GrokPs.ps1
# Client used by Grok Build (or a human) to talk to the Grok PowerShell sidecar.

[CmdletBinding()]
param(
    [ValidateSet('status', 'say', 'exec', 'inbox', 'ping')]
    [string]$Action = 'status',
    [string]$Text,
    [string]$Command,
    [string]$Cwd,
    [int]$TimeoutSec = 60,
    [string]$BaseUrl
)

$ErrorActionPreference = 'Stop'

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
        $params.Body = ($Body | ConvertTo-Json -Depth 8 -Compress)
    }
    try {
        return Invoke-RestMethod @params
    } catch {
        throw "Bridge unreachable at $Url. Start Scripts\Start-GrokPsBridge.ps1 first. $_"
    }
}

if (-not $BaseUrl) { $BaseUrl = Read-BridgeUrl }
$BaseUrl = $BaseUrl.TrimEnd('/')

switch ($Action) {
    'status' {
        $h = Invoke-BridgeApi GET "$BaseUrl/health"
        $h | ConvertTo-Json -Depth 6
    }
    'ping' {
        $h = Invoke-BridgeApi GET "$BaseUrl/health"
        Write-Output "pong $($h.bind) pid=$($h.pid)"
    }
    'say' {
        if (-not $Text) { throw 'say requires -Text' }
        $r = Invoke-BridgeApi POST "$BaseUrl/say" @{ from = 'grok-build'; to = 'grok-ps'; text = $Text }
        $r | ConvertTo-Json -Depth 6
    }
    'exec' {
        if (-not $Command) { throw 'exec requires -Command' }
        $payload = @{ from = 'grok-build'; cmd = $Command; timeout_sec = $TimeoutSec }
        if ($Cwd) { $payload.cwd = $Cwd }
        $r = Invoke-BridgeApi POST "$BaseUrl/exec" $payload
        $r | ConvertTo-Json -Depth 6
    }
    'inbox' {
        $r = Invoke-BridgeApi GET "$BaseUrl/inbox?role=grok-build"
        $r | ConvertTo-Json -Depth 8
    }
}
