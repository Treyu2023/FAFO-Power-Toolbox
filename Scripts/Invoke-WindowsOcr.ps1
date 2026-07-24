# Windows.Media.Ocr wrapper for FAFO Commander site survey photo ingest.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File Invoke-WindowsOcr.ps1 -ImagePath C:\path\to\shot.png
param(
  [Parameter(Mandatory = $true)]
  [string]$ImagePath,
  [string]$Lang = "en-US"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq "AsTask" -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1"
})[0]

function Await-WinRT($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $null = $netTask.Wait(-1)
  return $netTask.Result
}

[Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null

if (-not (Test-Path -LiteralPath $ImagePath)) {
  throw "Image not found: $ImagePath"
}

$full = (Resolve-Path -LiteralPath $ImagePath).Path
$engine = $null
try {
  $language = [Windows.Globalization.Language]::new($Lang)
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
} catch {
  $engine = $null
}
if (-not $engine) {
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if (-not $engine) {
  throw "No Windows OCR language pack available. Install English OCR under Windows Settings > Time & language > Language."
}

$file = Await-WinRT ([Windows.Storage.StorageFile]::GetFileFromPathAsync($full)) ([Windows.Storage.StorageFile])
$stream = Await-WinRT ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await-WinRT ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await-WinRT ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await-WinRT ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

$text = $result.Text
if (-not $text) {
  $lines = New-Object System.Collections.Generic.List[string]
  foreach ($line in $result.Lines) {
    [void]$lines.Add($line.Text)
  }
  $text = ($lines -join [Environment]::NewLine)
}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output $text
