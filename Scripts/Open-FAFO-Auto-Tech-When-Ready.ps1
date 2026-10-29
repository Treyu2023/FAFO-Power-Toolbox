# Hidden helper. Opens the standalone shop only after it identifies itself.
$ErrorActionPreference = 'SilentlyContinue'
$Url = 'http://127.0.0.1:8080/'
$Chrome = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
$deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $deadline) {
    try {
        $body = (Invoke-WebRequest -Uri 'http://127.0.0.1:8080/fafo-app.txt' -UseBasicParsing -TimeoutSec 2).Content.Trim()
        if ($body -ne 'fafo-auto-tech') { throw 'wrong app' }
        if (Test-Path -LiteralPath $Chrome) {
            Start-Process -FilePath $Chrome -ArgumentList "--app=$Url"
        } else {
            Start-Process $Url
        }
        exit 0
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
exit 1
