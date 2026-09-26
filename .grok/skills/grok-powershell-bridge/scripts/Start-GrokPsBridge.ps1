# Start-GrokPsBridge.ps1
# Persistent Grok PowerShell sidecar. Loopback HTTP + file mailbox.
# Leave this window open so Grok Build can talk to this session.

[CmdletBinding()]
param(
    [string]$BindHost = '127.0.0.87',
    [int]$Port = 17321,
    [string]$ToolboxRoot
)

$ErrorActionPreference = 'Stop'

function Get-BridgeRoots {
    $local = Join-Path $env:LOCALAPPDATA 'FAFO\GrokPsBridge'
    $homeBridge = Join-Path $env:USERPROFILE '.grok\ps-bridge'
    foreach ($name in @('inbox', 'outbox', 'archive')) {
        New-Item -ItemType Directory -Force -Path (Join-Path $local $name) | Out-Null
        New-Item -ItemType Directory -Force -Path (Join-Path $homeBridge $name) | Out-Null
    }
    [pscustomobject]@{ Local = $local; Home = $homeBridge }
}

function Write-EnvelopeFile {
    param($Envelope, [string]$Folder)
    $id = $Envelope.id
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmss')
    $name = "$stamp-$id.json"
    $json = $Envelope | ConvertTo-Json -Depth 8 -Compress
    Set-Content -LiteralPath (Join-Path $Folder $name) -Value $json -Encoding UTF8
}

function Mirror-File {
    param([string]$Source, [string]$DestDir)
    if (-not (Test-Path -LiteralPath $DestDir)) {
        New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination (Join-Path $DestDir (Split-Path $Source -Leaf)) -Force
}

function New-Envelope {
    param(
        [string]$From = 'grok-ps',
        [string]$To = 'grok-build',
        [string]$Kind = 'say',
        [string]$Text,
        [string]$Cmd,
        [string]$Cwd,
        [int]$TimeoutSec = 60,
        [object]$Ok,
        [string]$Stdout,
        [string]$Stderr,
        [object]$ExitCode,
        [string]$Id
    )
    if (-not $Id) { $Id = [guid]::NewGuid().ToString('N') }
    $o = [ordered]@{
        v           = 1
        id          = $Id
        ts          = (Get-Date).ToUniversalTime().ToString('o')
        from        = $From
        to          = $To
        kind        = $Kind
        timeout_sec = $TimeoutSec
    }
    if ($Text) { $o.text = $Text }
    if ($Cmd) { $o.cmd = $Cmd }
    if ($Cwd) { $o.cwd = $Cwd }
    if ($null -ne $Ok) { $o.ok = [bool]$Ok }
    if ($null -ne $Stdout) { $o.stdout = $Stdout }
    if ($null -ne $Stderr) { $o.stderr = $Stderr }
    if ($null -ne $ExitCode) { $o.exit_code = [int]$ExitCode }
    return [pscustomobject]$o
}

function Invoke-BridgeExec {
    param([string]$Cmd, [string]$Cwd, [int]$TimeoutSec = 60)
    if ([string]::IsNullOrWhiteSpace($Cmd)) {
        return [pscustomobject]@{ ok = $false; stdout = ''; stderr = 'empty cmd'; exit_code = 2 }
    }
    $lower = $Cmd.ToLowerInvariant()
    $blocked = @(
        'remove-item -recurse',
        'format ',
        'git push --force',
        'rm -rf /',
        'rmdir /s'
    )
    foreach ($b in $blocked) {
        if ($lower.Contains($b)) {
            return [pscustomobject]@{
                ok        = $false
                stdout    = ''
                stderr    = "blocked destructive pattern: $b (confirm in an interactive session)"
                exit_code = 4
            }
        }
    }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    $psi.FileName = if ($pwsh) { $pwsh.Source } else { (Get-Command powershell).Source }
    $psi.Arguments = "-NoProfile -NonInteractive -Command $Cmd"
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    if ($Cwd -and (Test-Path -LiteralPath $Cwd)) { $psi.WorkingDirectory = $Cwd }
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    if (-not $p.WaitForExit([Math]::Max(1000, $TimeoutSec * 1000))) {
        try { $p.Kill() } catch { }
        return [pscustomobject]@{ ok = $false; stdout = ''; stderr = "timeout after ${TimeoutSec}s"; exit_code = 124 }
    }
    $out = $p.StandardOutput.ReadToEnd()
    $err = $p.StandardError.ReadToEnd()
    return [pscustomobject]@{
        ok        = ($p.ExitCode -eq 0)
        stdout    = $out
        stderr    = $err
        exit_code = $p.ExitCode
    }
}

function Read-JsonBody([System.Net.HttpListenerRequest]$Req) {
    $reader = New-Object System.IO.StreamReader($Req.InputStream, $Req.ContentEncoding)
    try {
        $raw = $reader.ReadToEnd()
    } finally {
        $reader.Close()
    }
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return $raw | ConvertFrom-Json
}

function Write-JsonResponse([System.Net.HttpListenerResponse]$Res, $Obj, [int]$Status = 200) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($Obj | ConvertTo-Json -Depth 8))
    $Res.StatusCode = $Status
    $Res.ContentType = 'application/json; charset=utf-8'
    $Res.ContentLength64 = $bytes.Length
    $Res.OutputStream.Write($bytes, 0, $bytes.Length)
    $Res.OutputStream.Close()
}

function Get-Pending([string]$Dir) {
    if (-not (Test-Path -LiteralPath $Dir)) { return @() }
    Get-ChildItem -LiteralPath $Dir -Filter '*.json' -File | Sort-Object Name | ForEach-Object {
        try { Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json } catch { $null }
    } | Where-Object { $_ }
}

$roots = Get-BridgeRoots
if (-not $ToolboxRoot) {
    if ($env:FAFO_TOOLBOX_ROOT) { $ToolboxRoot = $env:FAFO_TOOLBOX_ROOT }
    else { $ToolboxRoot = Split-Path -Parent $PSScriptRoot }
}

$listener = [System.Net.HttpListener]::new()
$prefixes = @(
    "http://${BindHost}:${Port}/",
    "http://127.0.0.1:${Port}/"
)
$bound = $null
foreach ($prefix in $prefixes) {
    try {
        $listener.Prefixes.Clear()
        $listener.Prefixes.Add($prefix)
        $listener.Start()
        $bound = $prefix
        break
    } catch {
        $listener = [System.Net.HttpListener]::new()
    }
}
if (-not $bound) {
    throw "Could not bind loopback port $Port. Is another bridge already running?"
}

$meta = [ordered]@{
    v        = 1
    pid      = $PID
    bind     = $bound.TrimEnd('/')
    host     = $BindHost
    port     = $Port
    mailbox  = $roots.Local
    mirror   = $roots.Home
    toolbox  = $ToolboxRoot
    started  = (Get-Date).ToUniversalTime().ToString('o')
}
$metaJson = ($meta | ConvertTo-Json -Depth 5)
Set-Content -LiteralPath (Join-Path $roots.Local 'bridge.json') -Value $metaJson -Encoding UTF8
Set-Content -LiteralPath (Join-Path $roots.Home 'bridge.json') -Value $metaJson -Encoding UTF8

Write-Host "Grok PowerShell bridge listening on $($meta.bind)" -ForegroundColor Cyan
Write-Host "Mailbox: $($roots.Local)" -ForegroundColor Gray
Write-Host "Mirror : $($roots.Home)" -ForegroundColor Gray
Write-Host "Ctrl+C to stop." -ForegroundColor DarkGray

$hello = New-Envelope -Kind say -Text "Grok PowerShell bridge online at $($meta.bind)"
Write-EnvelopeFile -Envelope $hello -Folder (Join-Path $roots.Local 'outbox')
Write-EnvelopeFile -Envelope $hello -Folder (Join-Path $roots.Home 'outbox')

try {
    while ($listener.IsListening) {
        $ctxTask = $listener.GetContextAsync()
        while (-not $ctxTask.Wait(400)) {
            foreach ($boxRoot in @($roots.Local, $roots.Home)) {
                $inbox = Join-Path $boxRoot 'inbox'
                Get-ChildItem -LiteralPath $inbox -Filter '*.json' -File -ErrorAction SilentlyContinue | ForEach-Object {
                    try {
                        $msg = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
                        $archive = Join-Path $boxRoot 'archive'
                        Move-Item -LiteralPath $_.FullName -Destination (Join-Path $archive $_.Name) -Force
                        if ($msg.kind -eq 'exec' -and $msg.cmd) {
                            $result = Invoke-BridgeExec -Cmd $msg.cmd -Cwd $msg.cwd -TimeoutSec $(if ($msg.timeout_sec) { [int]$msg.timeout_sec } else { 60 })
                            $envRes = New-Envelope -Kind result -Id $msg.id -Text $msg.text -Cmd $msg.cmd -Cwd $msg.cwd -Ok $result.ok -Stdout $result.stdout -Stderr $result.stderr -ExitCode $result.exit_code
                            Write-EnvelopeFile -Envelope $envRes -Folder (Join-Path $roots.Local 'outbox')
                            Write-EnvelopeFile -Envelope $envRes -Folder (Join-Path $roots.Home 'outbox')
                        }
                    } catch {
                        Set-Content -LiteralPath (Join-Path $boxRoot 'last-error.json') -Value (@{ error = "$_" } | ConvertTo-Json) -Encoding UTF8
                    }
                }
            }
        }
        $ctx = $ctxTask.Result
        $req = $ctx.Request
        $res = $ctx.Response
        $path = $req.Url.AbsolutePath.TrimEnd('/').ToLowerInvariant()
        if ([string]::IsNullOrWhiteSpace($path)) { $path = '/' }
        try {
            switch ($path) {
                '/health' {
                    Write-JsonResponse $res $meta
                }
                '/say' {
                    $body = Read-JsonBody $req
                    $envSay = New-Envelope -From $(if ($body.from) { $body.from } else { 'grok-build' }) -To $(if ($body.to) { $body.to } else { 'grok-ps' }) -Kind say -Text $body.text
                    $target = if ($envSay.to -eq 'grok-build') { 'outbox' } else { 'inbox' }
                    if ($envSay.from -eq 'grok-ps') { $target = 'outbox' }
                    Write-EnvelopeFile -Envelope $envSay -Folder (Join-Path $roots.Local $target)
                    Write-EnvelopeFile -Envelope $envSay -Folder (Join-Path $roots.Home $target)
                    Write-Host "[say] $($envSay.from) -> $($envSay.to): $($envSay.text)" -ForegroundColor Green
                    Write-JsonResponse $res $envSay
                }
                '/exec' {
                    $body = Read-JsonBody $req
                    $cmd = [string]$body.cmd
                    $cwd = [string]$body.cwd
                    $timeout = if ($body.timeout_sec) { [int]$body.timeout_sec } else { 60 }
                    $result = Invoke-BridgeExec -Cmd $cmd -Cwd $cwd -TimeoutSec $timeout
                    $envRes = New-Envelope -From 'grok-ps' -To 'grok-build' -Kind result -Cmd $cmd -Cwd $cwd -Ok $result.ok -Stdout $result.stdout -Stderr $result.stderr -ExitCode $result.exit_code
                    Write-EnvelopeFile -Envelope $envRes -Folder (Join-Path $roots.Local 'outbox')
                    Write-EnvelopeFile -Envelope $envRes -Folder (Join-Path $roots.Home 'outbox')
                    Write-Host "[exec] $cmd  exit=$($result.exit_code)" -ForegroundColor Yellow
                    Write-JsonResponse $res $envRes
                }
                '/inbox' {
                    $role = $req.QueryString['role']
                    if ($role -eq 'grok-ps') {
                        Write-JsonResponse $res @{ items = @(Get-Pending (Join-Path $roots.Local 'inbox')) }
                    } else {
                        Write-JsonResponse $res @{ items = @(Get-Pending (Join-Path $roots.Local 'outbox')) }
                    }
                }
                '/reply' {
                    $body = Read-JsonBody $req
                    $envRep = New-Envelope -From $(if ($body.from) { $body.from } else { 'grok-ps' }) -To $(if ($body.to) { $body.to } else { 'grok-build' }) -Kind result -Id $body.id -Text $body.text -Ok $body.ok -Stdout $body.stdout -Stderr $body.stderr -ExitCode $body.exit_code
                    Write-EnvelopeFile -Envelope $envRep -Folder (Join-Path $roots.Local 'outbox')
                    Write-EnvelopeFile -Envelope $envRep -Folder (Join-Path $roots.Home 'outbox')
                    Write-JsonResponse $res $envRep
                }
                default {
                    Write-JsonResponse $res @{ error = "unknown path $path"; bind = $meta.bind } 404
                }
            }
        } catch {
            Write-JsonResponse $res @{ error = "$_" } 500
        }
    }
} finally {
    try { $listener.Stop() } catch { }
    try { $listener.Close() } catch { }
}
