# Add-GrokCLI-ToToolbox.ps1
# Adds a secure, cyberpunk-styled Grok Build CLI integration card to your AI HTML TOOLBOX.
# Path: C:\Users\rkey2\OneDrive\Desktop\AI HTML TOOLBOX
# Creates automatic backup before editing.
# Run in PowerShell (pwsh or Windows PowerShell). Close any open editors/browsers on the HTML file first.

param(
    [string]$ToolboxFolder = "C:\Users\rkey2\OneDrive\Desktop\AI HTML TOOLBOX",
    [switch]$DryRun = $false
)

$ErrorActionPreference = 'Stop'

Write-Host "=== Grok Build CLI Integration Tool ===" -ForegroundColor Cyan
Write-Host "Target folder: $ToolboxFolder" -ForegroundColor Gray

if (-not (Test-Path $ToolboxFolder)) {
    Write-Error "Folder not found: $ToolboxFolder"
    exit 1
}

# Find HTML files
$htmlFiles = Get-ChildItem -Path $ToolboxFolder -Filter "*.html" -File | Sort-Object Name
if ($htmlFiles.Count -eq 0) {
    Write-Error "No .html files found in the folder."
    exit 1
}

Write-Host "`nFound HTML file(s):" -ForegroundColor Yellow
$htmlFiles | ForEach-Object { Write-Host "  $($_.Name)" }

# Let user pick if multiple
if ($htmlFiles.Count -gt 1) {
    $selected = $htmlFiles | Out-GridView -Title "Select your main toolbox HTML file" -PassThru
    if (-not $selected) {
        Write-Host "No file selected. Exiting." -ForegroundColor Red
        exit 0
    }
    $targetFile = $selected.FullName
} else {
    $targetFile = $htmlFiles[0].FullName
}

Write-Host "`nSelected file: $targetFile" -ForegroundColor Green

# Backup
$backupDir = Join-Path $ToolboxFolder "backups"
if (-not (Test-Path $backupDir)) { New-Item -Path $backupDir -ItemType Directory -Force | Out-Null }
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = Join-Path $backupDir "$($htmlFiles[0].BaseName)_backup_$timestamp.html"
Copy-Item $targetFile $backupFile -Force
Write-Host "✅ Backup created: $backupFile" -ForegroundColor Green

# Read current content
$content = Get-Content $targetFile -Raw -Encoding UTF8

# The Grok CLI Card (cyberpunk / neon / terminal aesthetic matching FAFO Progen)
$grokCard = @'
<!-- ==================== GROK BUILD CLI CARD (Added $(Get-Date)) ==================== -->
<!-- Cyberpunk neon card for xAI Grok Build CLI integration -->
<!-- Security-first design • Review all agent actions • Scoped permissions recommended -->
<div class="grok-card group relative overflow-hidden rounded-2xl border border-cyan-500/30 bg-zinc-950/90 p-6 shadow-2xl shadow-cyan-950/50 backdrop-blur-sm transition-all hover:border-cyan-400/60 hover:shadow-cyan-500/20" style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;">
    
    <!-- Neon header -->
    <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-400 to-cyan-600 text-black shadow-lg shadow-cyan-500/50">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2" />
                </svg>
            </div>
            <div>
                <div class="text-2xl font-bold tracking-[3px] text-cyan-400">GROK BUILD</div>
                <div class="text-[10px] text-cyan-500/70 -mt-1">xAI CLI • v$(grok --version 2>$null || echo 'latest')</div>
            </div>
        </div>
        <div class="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-mono border border-emerald-500/30">SUPER GROK READY</div>
    </div>

    <p class="text-sm text-zinc-400 mb-5 leading-relaxed">
        Official xAI terminal coding agent &amp; TUI. Plan • Subagents • Headless scripting • Persistent memory.<br>
        Perfect for <span class="text-cyan-400">Progen development</span>, Suno lyrics, Imagine video prompts, CapCut pipelines, and FAFO Petro tooling.
    </p>

    <!-- Quick Actions -->
    <div class="mb-5">
        <div class="text-xs uppercase tracking-widest text-cyan-500/70 mb-2">QUICK ACTIONS — Copy &amp; Paste into PowerShell</div>
        <div class="grid grid-cols-2 gap-2 text-sm">
            <button onclick="navigator.clipboard.writeText('grok')" 
                    class="flex items-center justify-center gap-2 rounded-xl border border-cyan-500/30 bg-zinc-900 px-4 py-2.5 text-cyan-400 transition hover:bg-cyan-950 hover:border-cyan-400 active:scale-[0.985]">
                <span>🚀</span> <span class="font-medium">Launch TUI</span>
            </button>
            
            <button onclick="navigator.clipboard.writeText('grok -p \"Your prompt here\" --no-auto-update')" 
                    class="flex items-center justify-center gap-2 rounded-xl border border-cyan-500/30 bg-zinc-900 px-4 py-2.5 text-cyan-400 transition hover:bg-cyan-950 hover:border-cyan-400 active:scale-[0.985]">
                <span>⚡</span> <span class="font-medium">Headless Prompt</span>
            </button>
            
            <button onclick="navigator.clipboard.writeText('Start-Process pwsh -ArgumentList \"-NoExit\", \"-Command\", \"grok\"')" 
                    class="flex items-center justify-center gap-2 rounded-xl border border-cyan-500/30 bg-zinc-900 px-4 py-2.5 text-cyan-400 transition hover:bg-cyan-950 hover:border-cyan-400 active:scale-[0.985]">
                <span>🪟</span> <span class="font-medium">New Window</span>
            </button>
            
            <button onclick="navigator.clipboard.writeText('grok inspect')" 
                    class="flex items-center justify-center gap-2 rounded-xl border border-cyan-500/30 bg-zinc-900 px-4 py-2.5 text-cyan-400 transition hover:bg-cyan-950 hover:border-cyan-400 active:scale-[0.985]">
                <span>🔍</span> <span class="font-medium">Inspect Config</span>
            </button>
        </div>
    </div>

    <!-- Security & Memory -->
    <div class="rounded-xl border border-amber-500/20 bg-amber-950/10 p-4 text-xs mb-4">
        <div class="flex items-center gap-2 text-amber-400 font-semibold mb-1.5">
            <span>🛡️</span> <span>SECURITY FIRST (Non-Negotiable)</span>
        </div>
        <ul class="text-amber-300/90 space-y-0.5 pl-1 text-[13px]">
            <li>• Use <span class="font-mono text-amber-400">XAI_API_KEY</span> user environment variable (never hardcode)</li>
            <li>• Keep permission prompts ON — review every file change &amp; tool call</li>
            <li>• Add MCP filesystem <span class="font-mono">only</span> for specific folders (Progen, scripts, artifacts)</li>
            <li>• Review <span class="font-mono">grok mcp doctor</span> and <span class="font-mono">grok inspect</span> regularly</li>
            <li>• Sessions &amp; history live in <span class="font-mono">%USERPROFILE%\.grok\sessions</span> — export/delete old ones</li>
        </ul>
    </div>

    <!-- Memory & Best Practices -->
    <div class="text-xs text-zinc-400 mb-4">
        <span class="font-semibold text-cyan-400">PERSISTENT MEMORY:</span> Create <span class="font-mono text-white">AGENTS.md</span> in project roots with your rules (Progen modular blocks, cyberpunk neon, Suno structure, petroleum tech accuracy). Use <span class="font-mono">--session-id Progen-Dev</span> or <span class="font-mono">-c</span> to continue context across days.
    </div>

    <!-- Catch-up Prompt -->
    <div class="pt-3 border-t border-white/10">
        <button onclick="navigator.clipboard.writeText('I just added you to my local AI HTML TOOLBOX at C:\\Users\\rkey2\\OneDrive\\Desktop\\AI HTML TOOLBOX. My main projects: FAFO Progen Reimagined (cyberpunk prompt generator PWA), Suno/Imagine/CapCut content pipeline for @rwkey YouTube, FAFO Petro Services (Gilbarco/Verifone/Veeder-Root work). Run the Inspect-GrokInstall.ps1 diagnostic on my machine and then help me maximize your capabilities for my workflow while keeping security tight.')" 
                class="w-full rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-xs text-white/80 hover:bg-white/10 active:bg-white/5 transition flex items-center justify-center gap-2">
            <span>📋</span> 
            <span>COPY CATCH-UP PROMPT (paste into grok TUI or -p)</span>
        </button>
    </div>

    <div class="mt-4 text-[10px] text-center text-zinc-500">
        Official docs: <a href="https://docs.x.ai/build/overview" target="_blank" class="text-cyan-400 hover:underline">docs.x.ai/build/overview</a> • Update with <span class="font-mono">grok update</span>
    </div>
</div>
<!-- ==================== END GROK BUILD CLI CARD ==================== -->
'@

# Replace placeholder date
$grokCard = $grokCard -replace '\$\(Get-Date\)', (Get-Date -Format 'yyyy-MM-dd HH:mm')

if ($DryRun) {
    Write-Host "`n[DRY RUN] Card would be inserted. Preview saved to console only." -ForegroundColor Yellow
    Write-Host $grokCard
    exit 0
}

# Insert before </body>
if ($content -notmatch '</body>') {
    Write-Warning "No </body> tag found. Appending card to end of file instead."
    $newContent = $content + "`n`n" + $grokCard
} else {
    $newContent = $content -replace '(?i)</body>', "$grokCard`n</body>"
}

# Write back
Set-Content -Path $targetFile -Value $newContent -Encoding UTF8 -NoNewline
Write-Host "`n✅ SUCCESS! Grok Build CLI card has been added to your toolbox." -ForegroundColor Green
Write-Host "File: $targetFile" -ForegroundColor White
Write-Host "Backup: $backupFile" -ForegroundColor Gray

Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Open the HTML file in your browser or editor and move the new card to your preferred grid/section." -ForegroundColor White
Write-Host "2. Run the diagnostic script (Inspect-GrokInstall.ps1) if you haven't already." -ForegroundColor White
Write-Host "3. (Optional) Use the Prompt-GrokForToolbox script to have Grok itself suggest further refinements now that it's 'in' your toolbox." -ForegroundColor White
Write-Host "4. Test by copying one of the quick action commands into PowerShell." -ForegroundColor White

Write-Host "`nSecurity reminder: The card emphasizes least-privilege. Add MCP access only for folders you explicitly trust." -ForegroundColor Yellow