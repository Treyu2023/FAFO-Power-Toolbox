# AGENTS.md — FAFO Power Toolbox

Rules for **Grok CLI**, other coding agents, and humans working in this tree.

## Mission

Local, secure FAFO Power Toolbox + AI HTML Toolbox. Prefer small, reversible PowerShell/Python changes. Do not turn this into a cloud SaaS project.

## Non-negotiable security

1. **Never commit secrets.** That includes API keys, tokens, passwords, and any decrypted secret material.
2. **Never commit** `server/security_config.json` with a real key. Prefer non-secret flags only (e.g. `has_abuse_ch_key`). Real keys live in DPAPI under `%LOCALAPPDATA%\FAFO\Secrets\`.
3. **Always use FAFO.Secrets** (`Scripts\Modules\FAFO.Secrets`) for secret store/load:
   - `Set-FAFOSecret` / `Set-FAFOSecretFromPlainText`
   - `Get-FAFOSecret` / `Test-FAFOSecret`
   - `Initialize-FAFOEnvironment`
4. **Never print secret values** in reports, logs, status output, commits, or chat. Presence checks only (`Test-FAFOSecret`, `has_*` flags).
5. **Secret load order** for abuse.ch / similar: process env → DPAPI store → empty. Do **not** fall back to JSON for the real key.
6. Before any private remote push: run `Scripts\Invoke-FAFOPrePushCheck.ps1`.

## Code layout

| Area | Prefer |
|------|--------|
| PowerShell modules | `Scripts\Modules\FAFO.*\` |
| Session bootstrap | `Scripts\Initialize-FAFOSession.ps1` |
| Shared paths/reports/logs | `FAFO.Toolbox` helpers |
| Python backend | `server\` (loopback only) |
| Browser tools | existing HTML + `shared\` |
| Per-app edit snapshots | `snapshots\<relative-path-of-file>\` (newest **5 per app**) |

- Prefer **extending modules** over one-off scripts when a helper will be reused.
- Keep modules focused; do not dump unrelated utilities into `FAFO.Toolbox`.

## Per-app HTML snapshots

Undo copies stay **in this git folder** so agents can see them. **Keep is per app, not global.**

- **Path:** `snapshots/<relative-path-of-the-live-file>/`  
  Example: `snapshots/Typing Assistant Trainer.html/t62k3-20260824.html`
- **Retention:** newest **5 files in that app’s folder only**. Pruning one tool never drops another (backburner work stays).
- **Never** write `*.bak*` next to a live HTML/JS/CSS file. If a sidecar appears, move it with `.\Scripts\Consolidate-HtmlEditBackups.ps1`.
- Before editing a tool, copy the current file into **that tool’s** snapshots folder, then drop only the oldest file **in that folder** if it already has 5.
- Do not commit snapshots of gitignored private apps (TaxForge, Investor Portal).
- Policy file: `snapshots/README.md`.

## What must stay out of git

Do not add, stage, or commit:

- `Reports\`, `Logs\`, `Backups\`, `terminals\`
- `%LOCALAPPDATA%\FAFO\Secrets\` and `%LOCALAPPDATA%\FAFO\Devices\` (per-PC data)
- `System Tools\PC Reports and Log Viewer\catalog.js` / `logs-data.js` (generated per device)
- `server\security_config.json` with secrets
- `*.db`, `*.log`, thumbnails, quarantine, `__pycache__`
- `.env` and credential files
- **Any other machine’s diagnostic dumps** (desktop logs on a laptop clone, etc.)

Use `.gitignore` as the source of truth. If something sensitive appears, fix ignore rules and scrub history before pushing.

## Device-local reports & diagnostics

- **Each PC keeps its own reports/logs** under `%LOCALAPPDATA%\FAFO\Devices\<COMPUTERNAME>\`.
- Do **not** commit or copy another host’s packs into the shared repo for “convenience.”
- When the user asks for system health, PC status, diagnostics, or report library refresh — **run the full suite** without requiring them to name individual tests:

```powershell
& ".\Scripts\Initialize-FAFOSession.ps1"
Invoke-FAFOSystemDiagnostics -OpenHud   # uses .venv Python engine when available
# UI: System Tools\PC Diagnostics HUD.html  (configurable modules + interactive map)
# API: POST /api/pc-diagnostics/run
```

- Diagnostics write **device-local** reports (JSON/MD/HTML) under `%LOCALAPPDATA%\FAFO\Devices\<PC>\Reports\PC\`, with plain-English component IDs, compatibility notes, bottlenecks, and suggested fixes.

## Runtime / bind conventions

- Toolbox server bind: **`127.0.0.87:18765`** (see `shared\aitoolbox-bind.json`).
- Do **not** move it back to `127.0.0.1:8765` — that conflicts with FAFO companion.
- Secrets and machine-local state belong under `%LOCALAPPDATA%\FAFO\`, not OneDrive if avoidable.
- **Python:** use local **`.venv`** only (never global pip). Setup: `INSTALL-PYTHON.bat` / `Scripts\Install-PythonEnvironment.ps1`. Launchers resolve via `Scripts\use-fafo-python.bat`. See `docs\PYTHON-SETUP.md`.

## Safety & destructive actions

**Confirm with the user before:**

- Deleting files/folders outside disposable report/log cleanup
- `git push --force`, history rewrite, or remote repo creation/deletion
- Registry/system changes, elevated cleaners, mass device removal
- Rotating or overwriting secrets without an explicit request
- Packaging/publishing a distributable that might include data dirs

Prefer:

- `Backup-FAFOItem` / `Move-FAFOItem` (backup + no overwrite without `-Force`)
- `Remove-FAFOReport` with `-WhatIf` first when cleaning reports
- Explicit paths; avoid broad `Remove-Item -Recurse` at toolbox root

## Daily workflow (agents)

```powershell
& ".\Scripts\Initialize-FAFOSession.ps1"
Test-FAFOHealth
# work...
& ".\Scripts\Invoke-FAFOPrePushCheck.ps1"
```

Reports: `Write-FAFOReport` / `Write-FAFOStatusReport` → `%LOCALAPPDATA%\FAFO\Devices\<PC>\Reports\...` (this machine only).  
System diagnostics: `Invoke-FAFOSystemDiagnostics` → same device store + PC Report Library packs.

## PR / commit hygiene

- Small commits with clear intent.
- Do not commit generated reports “for convenience.”
- Do not embed absolute machine paths in committed config unless required and already project convention.
- After secret-related work, double-check `git status` and the pre-push check.

## When unsure

Ask the user. Local toolbox > clever automation that risks data loss or secret leakage.
