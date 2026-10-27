# Hidden helper. Opens the Auto Tech window after port 8080 answers.
$ErrorActionPreference = 'SilentlyContinue'
$Url = 'http://127.0.0.1:8080/?shop=1'
$Chrome = Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
$deadline = (Get-Date).AddMinutes(3)
while ((Get-Date) -lt $deadline) {
    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
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
