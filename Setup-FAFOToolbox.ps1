# Setup-FAFOToolbox.ps1
# One-time setup for FAFO Power Toolbox structure

Write-Host "=== Setting up FAFO Power Toolbox ===" -ForegroundColor Cyan

$root = "C:\Users\rkey2\OneDrive\Desktop\AI HTML TOOLBOX"

# 1. Create module folder
$secretsModule = Join-Path $root "Scripts\Modules\FAFO.Secrets"
New-Item -Path $secretsModule -ItemType Directory -Force | Out-Null

# 2. Create .gitignore
$gitignore = @"
# Secrets
.env
.env.*
server/security_config.json
**/Secrets/
*auth_key*
*api_key*

# Reports & generated data
Reports/
backups/
terminals/
*.log
*.db
Logs*/

# Python
__pycache__/
*.pyc
venv/
.venv/

# Misc
.vscode/
.idea/
.DS_Store
"@
$gitignore | Out-File (Join-Path $root ".gitignore") -Encoding UTF8 -Force

# 3. Create report folders
New-Item -Path (Join-Path $root "Reports\Markdown") -ItemType Directory -Force | Out-Null
New-Item -Path (Join-Path $root "Reports\Raw") -ItemType Directory -Force | Out-Null

Write-Host "✅ Folders and .gitignore created." -ForegroundColor Green
Write-Host "Next: I'll give you the FAFO.Secrets module files to paste." -ForegroundColor Yellow